import difflib
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db_session
from src.models.catalog import GameModel, TrophyModel
from src.models.chunk import GuideChunkModel
from src.models.player import PlayerModel, PlayerGameModel, PlayerTrophyModel
from src.services.entity_linker import normalize_for_matching, get_canonical_game_id

router = APIRouter(prefix="/api/v1/catalog", tags=["Catalog"])


async def resolve_game_record(session: AsyncSession, game: str) -> Optional[GameModel]:
    clean = game.strip()
    slug = get_canonical_game_id(clean)
    stmt = (
        select(GameModel)
        .where(
            (GameModel.id == clean.lower())
            | (GameModel.id == slug)
            | (GameModel.title.ilike(clean))
            | (GameModel.aliases.contains([clean]))
        )
        .limit(1)
    )
    res = (await session.execute(stmt)).scalars().first()
    if res:
        return res
    stmt_partial = select(GameModel).where(GameModel.title.ilike(f"%{clean}%")).limit(1)
    return (await session.execute(stmt_partial)).scalars().first()


@router.get("/trophy-guide")
async def get_trophy_guide(
    game: str = Query(..., description="Canonical game id, title or alias"),
    trophy: str = Query(..., description="Official trophy name in English"),
) -> Dict[str, Any]:
    """
    Resolves trophy metadata and returns ordered guide chunks without vector search.
    Supports exact match, alias match, or fuzzy suggestion candidates.
    """
    async with get_db_session() as session:
        game_record = await resolve_game_record(session, game)
        if not game_record:
            raise HTTPException(status_code=404, detail=f"Game '{game}' not found in catalog.")

        stmt_trophies = select(TrophyModel).where(TrophyModel.game_id == game_record.id)
        all_trophies = (await session.execute(stmt_trophies)).scalars().all()

        norm_query = normalize_for_matching(trophy)
        matched_trophy: Optional[TrophyModel] = None

        for t in all_trophies:
            if normalize_for_matching(t.name) == norm_query or t.name.lower() == trophy.strip().lower():
                matched_trophy = t
                break
            if t.aliases and any(normalize_for_matching(a) == norm_query for a in t.aliases):
                matched_trophy = t
                break

        if matched_trophy:
            # Order chunks deterministically by source and chunk id
            stmt_chunks = (
                select(GuideChunkModel)
                .where(GuideChunkModel.trophy_id == matched_trophy.id)
                .order_by(GuideChunkModel.source_url.asc(), GuideChunkModel.id.asc())
            )
            chunks = (await session.execute(stmt_chunks)).scalars().all()

            return {
                "status": "found",
                "game": game_record.title,
                "trophy": {
                    "id": matched_trophy.id,
                    "game_id": matched_trophy.game_id,
                    "psn_trophy_id": matched_trophy.psn_trophy_id,
                    "name": matched_trophy.name,
                    "type": matched_trophy.type,
                    "description": matched_trophy.description,
                    "dlc": matched_trophy.dlc,
                    "location": matched_trophy.location,
                    "missable": matched_trophy.missable,
                    "missable_sources": matched_trophy.missable_sources or [],
                    "aliases": matched_trophy.aliases or [],
                },
                "chunks": [
                    {
                        "id": c.id,
                        "title": c.title,
                        "content": c.content,
                        "source_url": c.source_url,
                        "is_missable": c.is_missable,
                        "context_prefix": c.context_prefix,
                    }
                    for c in chunks
                ],
                "linked_chunks_count": len(chunks),
                "has_guide": len(chunks) > 0,
            }

        # Fuzzy suggestion candidates
        trophy_names = [t.name for t in all_trophies]
        name_map = {normalize_for_matching(name): name for name in trophy_names}
        close_norm = difflib.get_close_matches(norm_query, list(name_map.keys()), n=5, cutoff=0.35)
        suggestions = [name_map[cn] for cn in close_norm]
        if not suggestions:
            suggestions = difflib.get_close_matches(trophy, trophy_names, n=5, cutoff=0.35)

        return {
            "status": "suggestions" if suggestions else "not_found",
            "game": game_record.title,
            "trophy": None,
            "suggestions": suggestions,
            "chunks": [],
            "linked_chunks_count": 0,
            "has_guide": False,
            "message": (
                f"Trophy '{trophy}' not found. Did you mean one of: {', '.join(suggestions)}?"
                if suggestions
                else f"Trophy '{trophy}' not found in catalog for game '{game_record.title}'."
            ),
        }


@router.get("/trophies")
async def list_catalog_trophies(
    game: str = Query(..., description="Canonical game id, title or alias"),
    type: Optional[str] = Query(None, description="Filter by type (bronze, silver, gold, platinum)"),
    dlc: Optional[str] = Query(None, description="Filter by DLC (e.g. 'Hearts of Stone', 'Base Game')"),
    location: Optional[str] = Query(None, description="Filter by location (e.g. 'Novigrad', 'Velen')"),
    missable: Optional[bool] = Query(None, description="Filter missables only"),
    missing_for_psn_id: Optional[str] = Query(None, description="Filter trophies pending for PSN ID"),
) -> Dict[str, Any]:
    """
    SQL-only structured filtering of catalog trophies. Returns complete lists and chunk coverage counts.
    """
    async with get_db_session() as session:
        game_record = await resolve_game_record(session, game)
        if not game_record:
            raise HTTPException(status_code=404, detail=f"Game '{game}' not found in catalog.")

        conditions = [TrophyModel.game_id == game_record.id]

        if type:
            conditions.append(TrophyModel.type == type.lower().strip())

        if dlc is not None:
            dlc_clean = dlc.strip()
            if dlc_clean.lower() in ("base", "base game", "none", "null"):
                conditions.append(TrophyModel.dlc.is_(None))
            else:
                conditions.append(TrophyModel.dlc.ilike(dlc_clean))

        if missable is not None:
            conditions.append(TrophyModel.missable.is_(missable))

        if location:
            loc_pattern = f"%{location.strip()}%"
            # Insight: Check trophy location or linked guide chunks matching location
            conditions.append(
                (TrophyModel.location.ilike(loc_pattern))
                | (
                    TrophyModel.id.in_(
                        select(GuideChunkModel.trophy_id).where(
                            (GuideChunkModel.trophy_id.is_not(None))
                            & (
                                (GuideChunkModel.context_prefix.ilike(loc_pattern))
                                | (GuideChunkModel.content.ilike(loc_pattern))
                                | (GuideChunkModel.title.ilike(loc_pattern))
                            )
                        )
                    )
                )
            )

        if missing_for_psn_id:
            unlocked_subq = (
                select(PlayerTrophyModel.trophy_id)
                .join(PlayerGameModel, PlayerGameModel.id == PlayerTrophyModel.player_game_id)
                .join(PlayerModel, PlayerModel.id == PlayerGameModel.player_id)
                .where(
                    PlayerModel.psn_id.ilike(missing_for_psn_id.strip()),
                    PlayerGameModel.game_title.ilike(f"%{game_record.title}%"),
                    PlayerTrophyModel.is_unlocked.is_(True),
                    PlayerTrophyModel.trophy_id.is_not(None),
                )
            )
            conditions.append(TrophyModel.id.notin_(unlocked_subq))

        stmt = select(TrophyModel).where(and_(*conditions)).order_by(TrophyModel.id.asc())
        trophies = (await session.execute(stmt)).scalars().all()

        chunk_counts_stmt = (
            select(GuideChunkModel.trophy_id, func.count(GuideChunkModel.id))
            .where(GuideChunkModel.game_id == game_record.id)
            .group_by(GuideChunkModel.trophy_id)
        )
        chunk_counts = dict((await session.execute(chunk_counts_stmt)).all())

        total_linked_chunks = sum(chunk_counts.get(t.id, 0) for t in trophies)
        has_guide = total_linked_chunks > 0

        return {
            "game_id": game_record.id,
            "total": len(trophies),
            "has_guide": has_guide,
            "linked_chunks_count": total_linked_chunks,
            "trophies": [
                {
                    "id": t.id,
                    "name": t.name,
                    "type": t.type,
                    "description": t.description,
                    "dlc": t.dlc,
                    "location": t.location,
                    "missable": t.missable,
                    "missable_sources": t.missable_sources or [],
                    "linked_chunks_count": chunk_counts.get(t.id, 0),
                }
                for t in trophies
            ],
        }


@router.get("/overview")
async def get_catalog_overview(
    game: str = Query(..., description="Canonical game id, title or alias"),
) -> Dict[str, Any]:
    """
    Returns high-level platinum overview: difficulty, hours, playthroughs, and counts by type and DLC.
    """
    async with get_db_session() as session:
        game_record = await resolve_game_record(session, game)
        if not game_record:
            raise HTTPException(status_code=404, detail=f"Game '{game}' not found in catalog.")

        stmt = select(TrophyModel).where(TrophyModel.game_id == game_record.id)
        trophies = (await session.execute(stmt)).scalars().all()

        # Type distribution
        by_type = {"bronze": 0, "silver": 0, "gold": 0, "platinum": 0}
        for t in trophies:
            t_type = (t.type or "bronze").lower()
            if t_type in by_type:
                by_type[t_type] += 1

        # Chunks per trophy for DLC guide coverage
        chunk_counts_stmt = (
            select(GuideChunkModel.trophy_id, func.count(GuideChunkModel.id))
            .where(GuideChunkModel.game_id == game_record.id)
            .group_by(GuideChunkModel.trophy_id)
        )
        chunk_counts = dict((await session.execute(chunk_counts_stmt)).all())

        dlc_groups: Dict[str, Dict[str, int]] = {}
        # Ensure Base Game is first
        dlc_groups["Base Game"] = {"count": 0, "linked_chunks_count": 0}

        for t in trophies:
            dlc_label = t.dlc if t.dlc else "Base Game"
            if dlc_label not in dlc_groups:
                dlc_groups[dlc_label] = {"count": 0, "linked_chunks_count": 0}
            dlc_groups[dlc_label]["count"] += 1
            dlc_groups[dlc_label]["linked_chunks_count"] += chunk_counts.get(t.id, 0)

        by_dlc = [
            {"name": name, "count": data["count"], "linked_chunks_count": data["linked_chunks_count"]}
            for name, data in dlc_groups.items()
        ]

        return {
            "game_id": game_record.id,
            "title": game_record.title,
            "difficulty": float(game_record.difficulty) if game_record.difficulty is not None else None,
            "hours": game_record.hours,
            "playthroughs": game_record.playthroughs,
            "metadata_source": game_record.metadata_source,
            "total_trophies": len(trophies),
            "by_type": by_type,
            "by_dlc": by_dlc,
        }
