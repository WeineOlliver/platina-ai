from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import hashlib
from sqlalchemy import select, func, delete
from src.database import get_db_session
from src.models.chunk import GuideChunkModel
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
        for page_title, page_markdown, page_url in pages:
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

        return {
            "status": "indexed",
            "game": request.game,
            "chunks_indexed": len(all_chunks),
            "pages_indexed": len(pages),
            "source_url": canonical_url,
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Erro na extração e indexação do guia: {str(e)}")
