from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import hashlib
import logging
from sqlalchemy import select, func, delete, update

logger = logging.getLogger(__name__)
from src.database import get_db_session
from src.models.chunk import GuideChunkModel
from src.models.player import PlayerGameModel, PlayerTrophyModel
from src.schemas.chunk import IngestGuideRequest, DocumentChunk, FetchAndIndexRequest
from src.schemas.search import SearchQueryRequest, SearchResponse
from src.services.chunker import chunker
from src.services.embedding import embedding_service
from src.services.ingestion import ingestion_repo
from src.services.scraper import scraper
from src.services.search import vector_search_service

router = APIRouter(prefix="/api/v1/ingest", tags=["Ingestion & Chunker"])


@router.post("/parse", response_model=List[DocumentChunk])
async def parse_and_chunk_guide(request: IngestGuideRequest):
    """
    Parses a PlayStation trophy guide and generates contextual semantic chunks
    with missable trophy auto-tagging.
    """
    try:
        chunks = chunker.chunk_guide(request)
        if not chunks:
            raise HTTPException(status_code=400, detail="O conteúdo fornecido não gerou blocos válidos.")
        return chunks
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Erro durante o processamento do guia: {str(e)}")


@router.post("/index", response_model=Dict[str, Any])
async def index_guide(request: IngestGuideRequest):
    """
    Complete pipeline: parses guide, computes dense vector embeddings,
    and stores chunks in PostgreSQL with pgvector.
    """
    try:
        chunks = chunker.chunk_guide(request)
        if not chunks:
            raise HTTPException(status_code=400, detail="Conteúdo insuficiente para indexação.")

        result = await ingestion_repo.ingest_chunks(chunks)
        return result
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Erro na indexação vetorial: {str(e)}")


@router.post("/search", response_model=SearchResponse)
async def semantic_search(request: SearchQueryRequest):
    """
    Executes semantic similarity search with optional hybrid filtering
    (game and missable_only) using pgvector.
    """
    try:
        return await vector_search_service.search(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na busca semântica: {str(e)}")


@router.post("/reindex", response_model=Dict[str, Any])
async def reindex_guide(request: IngestGuideRequest):
    """
    Atomically purges any existing guide chunks for the game
    and replaces them with fresh chunks and vector embeddings.
    """
    try:
        chunks = chunker.chunk_guide(request)
        if not chunks:
            raise HTTPException(status_code=400, detail="Conteúdo insuficiente para reindexação.")

        return await ingestion_repo.reindex_game(request.game, chunks)
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Erro na reindexação do guia: {str(e)}")


@router.post("/fetch-and-index", response_model=Dict[str, Any])
async def fetch_and_index_guide(request: FetchAndIndexRequest):
    """
    On-demand web scraper and ingestion pipeline.
    Checks if guide chunks already exist for the game; if not (or if force_reindex=True),
    fetches/scrapes the guide and all discovered subpages, chunks them semantically,
    embeds them, and stores chunks with pgvector and full-text search.
    """
    try:
        # 1. Check if game is already indexed (unless force_reindex is True)
        if not request.force_reindex:
            async with get_db_session() as session:
                stmt = select(func.count(GuideChunkModel.id)).where(GuideChunkModel.game.ilike(request.game.strip()))
                result = await session.execute(stmt)
                count = result.scalar() or 0
                if count > 0:
                    return {
                        "status": "already_indexed",
                        "chunks_indexed": count,
                    }

        # 2. Fetch main guide and all discovered subpages
        pages = await scraper.fetch_game_guide_with_subpages(request.game, source_url=request.source_url)
        if not pages:
            raise HTTPException(status_code=400, detail="Não foi possível obter o guia ou subpáginas.")

        # 3. Chunk each subpage via semantic markdown chunker
        all_chunks: List[DocumentChunk] = []
        global_idx = 0
        for page_title, page_markdown, page_url, _ in pages:
            ingest_req = IngestGuideRequest(game=request.game, source_url=page_url, content=page_markdown)
            chunks = chunker.chunk_guide(ingest_req)
            for c in chunks:
                c.metadata["page_title"] = page_title
                c.metadata["page_url"] = page_url
                # Ensure deterministic unique chunk_id across pages
                id_raw = f"{request.game}:{page_url}:{c.title}:{global_idx}:{c.content[:50]}"
                c.chunk_id = hashlib.sha256(id_raw.encode("utf-8")).hexdigest()[:24]
                global_idx += 1
            all_chunks.extend(chunks)

        if not all_chunks:
            raise HTTPException(status_code=400, detail="Conteúdo insuficiente para indexação.")

        # 4. Embed chunks in batch
        texts_to_embed = [f"{c.title}\n{c.content}" for c in all_chunks]
        embeddings = await embedding_service.embed_batch(texts_to_embed)

        # 5. Persist to PostgreSQL (atomic replace if force_reindex)
        canonical_url = pages[0][2] if pages else (request.source_url or "local")
        async with get_db_session() as session:
            if request.force_reindex:
                await session.execute(
                    delete(GuideChunkModel).where(GuideChunkModel.game.ilike(request.game.strip()))
                )
            for chunk, emb in zip(all_chunks, embeddings):
                record = GuideChunkModel(
                    id=chunk.chunk_id,
                    game=chunk.game,
                    title=chunk.title,
                    content=chunk.content,
                    is_missable=chunk.is_missable,
                    source_url=chunk.metadata.get("source_url", canonical_url),
                    metadata_=chunk.metadata,
                    embedding=emb,
                )
                session.add(record)

        # 6. Extract missable trophies from parsed pages & roadmap DOM, then update player_trophies
        discovered_missables: set[str] = set()
        for page_title, page_markdown, page_url, page_html in pages:
            dom_data = scraper.parse_roadmap_dom(page_html, base_url=page_url)
            for m in dom_data.get("missable_trophies", []):
                discovered_missables.add(m)

        for c in all_chunks:
            if c.is_missable and c.title:
                norm = scraper._normalize_trophy_name(c.title)
                if scraper._is_valid_trophy_name(norm):
                    discovered_missables.add(norm)

        updated_count = 0
        if discovered_missables:
            async with get_db_session() as session:
                game_clean = request.game.strip()
                pg_stmt = select(PlayerGameModel.id).where(
                    (PlayerGameModel.game_title.ilike(game_clean))
                    | (PlayerGameModel.game_title.ilike(f"%{game_clean}%"))
                )
                pg_res = await session.execute(pg_stmt)
                game_ids = [r[0] for r in pg_res.fetchall()]

                if not game_ids:
                    logger.warning("Nenhum player_game encontrado para o jogo '%s'; pulando sync de missáveis.", request.game)
                    updated_count = 0
                else:
                    lower_names = [m.lower().strip() for m in discovered_missables]
                    update_stmt = (
                        update(PlayerTrophyModel)
                        .where(
                            func.lower(PlayerTrophyModel.trophy_name).in_(lower_names),
                            PlayerTrophyModel.player_game_id.in_(game_ids),
                        )
                        .values(
                            is_missable=True,
                            trophy_category="missable"
                        )
                    )
                    res = await session.execute(update_stmt)
                    updated_count = res.rowcount or 0

        return {
            "status": "indexed",
            "game": request.game,
            "chunks_indexed": len(all_chunks),
            "pages_indexed": len(pages),
            "source_url": canonical_url,
            "missables_synced": list(discovered_missables),
            "trophies_updated": updated_count,
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Erro na extração e indexação do guia: {str(e)}")
