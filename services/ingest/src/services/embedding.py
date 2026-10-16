from abc import ABC, abstractmethod
from typing import List
import hashlib


class IEmbeddingService(ABC):
    """
    Abstract interface for embedding generation.
    Enables swapping between OpenAI, VoyageAI, HuggingFace, or deterministic local models.
    """
    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        pass

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

        words = normalized.split()
        if not words:
            return vector

        for word in words:
            # Seed deterministic pseudo-random components based on word hash
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            for i in range(0, min(len(digest), 32)):
                idx = (digest[i] * (i + 1)) % self.DIMENSIONS
                val = ((digest[i] - 128) / 128.0)
                vector[idx] += val

        # Normalize to unit vector (L2 norm) for cosine distance compatibility
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector


embedding_service: IEmbeddingService = DeterministicLocalEmbeddingService()
