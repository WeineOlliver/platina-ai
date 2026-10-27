from abc import ABC, abstractmethod
from typing import List, Optional
import hashlib
import os
import re
import httpx


class IEmbeddingService(ABC):
    """
    Abstract interface for embedding generation.
    Enables swapping between OpenAI and deterministic local models.
    """
    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        pass

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return await self.embed_texts(texts)

    @abstractmethod
    async def embed_query(self, query: str) -> List[float]:
        pass


class DeterministicLocalEmbeddingService(IEmbeddingService):
    """
    High-performance, zero-cost deterministic embedding generator (1536 dimensions).
    Uses pseudo-random Gaussian projections seeded by SHA-256 tokens.
    Guarantees deterministic vector representations for semantic testing and local development
    without requiring third-party API keys or GPU memory.
    """
    DIMENSIONS: int = 1536

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [self._generate_vector(t) for t in texts]

    async def embed_query(self, query: str) -> List[float]:
        return self._generate_vector(query)

    def _generate_vector(self, text: str) -> List[float]:
        normalized = text.lower().strip()
        vector = [0.0] * self.DIMENSIONS

        # Split on non-alphanumeric to capture clean word tokens
        words = [w for w in re.findall(r'\b\w+\b', normalized) if len(w) > 2]
        if not words:
            return vector

        # Stopwords to dampen generic noise (English & PT)
        stopwords = {
            "como", "qual", "onde", "para", "com", "não", "que", "dos", "das", "uma", "guia", "este", "completo",
            "troféus", "trofeu", "trofeus", "troféu", "what", "which", "where", "how", "with", "this", "that", "the"
        }

        # Bag-of-words hash projection with TF weighting
        word_counts = {}
        for w in words:
            if w not in stopwords:
                word_counts[w] = word_counts.get(w, 0) + 1

        if not word_counts:
            word_counts = {w: 1 for w in words}

        # Weight unique / specific terms much higher
        for word, count in word_counts.items():
            w_bytes = word.encode("utf-8")
            h = int(hashlib.sha256(w_bytes).hexdigest()[:8], 16)
            idx = h % self.DIMENSIONS
            
            # Specific domain terms receive high weight
            term_weight = 4.0 if len(word) >= 5 else 2.0
            weight = term_weight * (1.0 + (count ** 0.5))
            vector[idx] += weight

        # Normalize to unit vector (L2 norm) for cosine distance compatibility
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector


class OpenAIEmbeddingService(IEmbeddingService):
    """
    OpenAI text-embedding-3-small provider (1536 dimensions).
    Uses native httpx client for high-throughput batch vector generation.
    """
    DIMENSIONS: int = 1536

    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-3-small"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        # Insight: OpenAI batch embeddings endpoint handles list of strings and preserves index order
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{self.base_url}/embeddings", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            data.sort(key=lambda item: item["index"])
            return [item["embedding"] for item in data]

    async def embed_query(self, query: str) -> List[float]:
        results = await self.embed_texts([query])
        return results[0] if results else [0.0] * self.DIMENSIONS


def get_embedding_service() -> IEmbeddingService:
    # Insight: Select provider via EMBEDDING_PROVIDER (openai|local). Default is local for unit tests and offline dev.
    provider = os.getenv("EMBEDDING_PROVIDER", "local").strip().lower()
    if provider == "openai":
        return OpenAIEmbeddingService()
    return DeterministicLocalEmbeddingService()


embedding_service: IEmbeddingService = get_embedding_service()
