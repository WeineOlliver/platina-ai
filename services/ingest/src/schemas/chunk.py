from pydantic import BaseModel, Field
from typing import Dict, Any


class DocumentChunk(BaseModel):
    """
    Represents an atomic, contextual chunk of a trophy guide.
    Designed for embedding generation and pgvector similarity retrieval.
    """
    chunk_id: str = Field(..., description="Unique deterministic identifier for the chunk")
    game: str = Field(..., description="Game title (e.g., Bloodborne)")
    title: str = Field(..., description="Section, chapter, or trophy heading")
    content: str = Field(..., description="Cleaned contextual text payload")
    is_missable: bool = Field(default=False, description="Flag indicating if the chunk contains missable warnings")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context (source, chunk_index, etc.)")


class IngestGuideRequest(BaseModel):
    game: str = Field(..., min_length=2, max_length=100)
    source_url: str = Field(default="local", description="Original source guide URL or reference")
    content: str = Field(..., min_length=50, description="Raw markdown or text content of the trophy guide")
