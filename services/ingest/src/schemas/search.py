from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class SearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="User question or search query")
    game: Optional[str] = Field(default=None, description="Optional game filter")
    missable_only: bool = Field(default=False, description="Filter only chunks flagged as missable")
    limit: int = Field(default=3, ge=1, le=10, description="Number of top chunks to return")
    min_similarity: float = Field(default=0.65, ge=0.0, le=1.0, description="Minimum similarity threshold cutoff")


class SearchResultItem(BaseModel):
    id: str
    game: str
    title: str
    content: str
    is_missable: bool
    source_url: Optional[str]
    similarity_score: float = Field(..., description="Cosine similarity score (0.0 to 1.0, higher is better)")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    query: str
    total_results: int
    results: List[SearchResultItem]
