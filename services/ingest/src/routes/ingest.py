from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from src.schemas.chunk import IngestGuideRequest, DocumentChunk
from src.schemas.search import SearchQueryRequest, SearchResponse
from src.services.chunker import chunker
from src.services.ingestion import ingestion_repo
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
