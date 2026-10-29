import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.catalog import TrophyModel
from src.schemas.chunk import DocumentChunk
from src.services.chunker import build_context_prefix

logger = logging.getLogger(__name__)


def get_canonical_game_id(game: str) -> str:
    # Deterministic slug for canonical game id lookup
    slug = re.sub(r"[^\w\s-]", "", game.lower()).strip()
    return re.sub(r"[-\s]+", "-", slug)[:100]


def normalize_for_matching(text: str) -> str:
    """
    Normalizes chunk title or trophy name for deterministic entity linking:
    - Strips (Part N), - Part N, and parenthetical patch notes
    - Strips guide noise like Video Guide, Trophy Guide
    - Strips accents, unifies curly quotes, ellipses, and removes punctuation
    """
    if not text:
        return ""

    # Remove Part indicators: (Part 1), (Part 2), (Part 3 of 4), - Part 1, etc.
    t = re.sub(r"\s*\((?:part\s*\d+|pt\.?\s*\d+)(?:\s*of\s*\d+)?\)", "", text, flags=re.IGNORECASE)
    t = re.sub(r"\s*-\s*part\s*\d+", "", t, flags=re.IGNORECASE)

    # Remove parenthetical notes e.g. (works after patch 1.30)
    t = re.sub(r"\s*\(works after patch[^\)]*\)", "", t, flags=re.IGNORECASE)

    # Remove Video Guide / Trophy Guide suffixes
    t = re.sub(r"\s+(?:trophy\s+)?video\s+guide\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\s+(?:trophy\s+)?guide\b", "", t, flags=re.IGNORECASE)

    # Unicode NFKD decomposition to strip diacritics
    nfkd = unicodedata.normalize("NFKD", t)
    unaccented = "".join(c for c in nfkd if not unicodedata.combining(c))

    # Normalize quotes, curly quotes, and ellipses
    cleaned = (
        unaccented.lower()
        .replace("’", "")
        .replace("‘", "")
        .replace("'", "")
        .replace("“", "")
        .replace("”", "")
        .replace('"', "")
        .replace("…", "")
    )

    # Strip punctuation, keep alphanumeric and spaces
    cleaned = re.sub(r"[^a-z0-9\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


async def link_chunk_to_trophy(
    title: str,
    game_id: str,
    session: AsyncSession,
) -> Optional[TrophyModel]:
    """
    Links a single title to a canonical TrophyModel by matching against
    normalized trophy names and aliases for the specified game.
    """
    norm_target = normalize_for_matching(title)
    if not norm_target:
        return None

    clean_id = get_canonical_game_id(game_id)
    stmt = select(TrophyModel).where(
        (TrophyModel.game_id == game_id) | (TrophyModel.game_id == clean_id)
    )
    res = await session.execute(stmt)
    trophies = res.scalars().all()

    for t in trophies:
        if normalize_for_matching(t.name) == norm_target:
            return t
        for alias in (t.aliases or []):
            if normalize_for_matching(alias) == norm_target:
                return t

    return None


async def link_chunks_to_trophies(
    chunks: List[DocumentChunk],
    game_id: str,
    session: AsyncSession,
) -> Dict[str, Any]:
    """
    Links a collection of DocumentChunks to canonical trophies in PostgreSQL:
    - Sets chunk.trophy_id and chunk.metadata['trophy_id']
    - Updates chunk.context_prefix with canonical trophy.dlc
    - Logs count linked, count unlinked, and the unlinked titles list.
    """
    clean_id = get_canonical_game_id(game_id)
    stmt = select(TrophyModel).where(
        (TrophyModel.game_id == game_id) | (TrophyModel.game_id == clean_id)
    )
    res = await session.execute(stmt)
    trophies = res.scalars().all()

    lookup: Dict[str, TrophyModel] = {}
    for t in trophies:
        lookup[normalize_for_matching(t.name)] = t
        for alias in (t.aliases or []):
            lookup[normalize_for_matching(alias)] = t

    linked_count = 0
    unlinked_titles: List[str] = []

    for c in chunks:
        norm_title = normalize_for_matching(c.title)
        matched_trophy = lookup.get(norm_title)

        if matched_trophy:
            c.trophy_id = matched_trophy.id
            c.metadata["trophy_id"] = matched_trophy.id
            c.metadata["canonical_trophy_name"] = matched_trophy.name
            c.metadata["dlc"] = matched_trophy.dlc
            # Update hierarchical context prefix with canonical trophy dlc
            c.context_prefix = build_context_prefix(
                game=c.game,
                title=c.title,
                content=c.content,
                source_url=c.metadata.get("source_url", ""),
                dlc=matched_trophy.dlc or "Base Game",
            )
            linked_count += 1
        else:
            c.trophy_id = None
            c.context_prefix = build_context_prefix(
                game=c.game,
                title=c.title,
                content=c.content,
                source_url=c.metadata.get("source_url", ""),
                dlc=None,
            )
            unlinked_titles.append(c.title)

    logger.info(
        "Entity linking for game '%s': %d linked, %d unlinked.",
        game_id,
        linked_count,
        len(unlinked_titles),
    )
    print(f"[ENTITY LINKING] {game_id}: {linked_count} linked, {len(unlinked_titles)} unlinked. Unlinked: {unlinked_titles}")

    return {
        "game_id": game_id,
        "linked_count": linked_count,
        "unlinked_count": len(unlinked_titles),
        "unlinked_titles": unlinked_titles,
    }
