from fastapi import APIRouter, HTTPException
from typing import List
from src.schemas.chunk import IngestGuideRequest, DocumentChunk
from src.services.chunker import chunker

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
