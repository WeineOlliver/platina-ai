from abc import ABC, abstractmethod
from typing import List
import hashlib
import re


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

        # Split on non-alphanumeric to capture clean word tokens
        words = [w for w in re.findall(r'\b\w+\b', normalized) if len(w) > 2]
        if not words:
            return vector

        # Stopwords to dampen generic noise
        stopwords = {"como", "qual", "onde", "para", "com", "não", "que", "dos", "das", "uma", "guia", "este", "completo", "troféus", "trofeu", "trofeus", "troféu"}

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
            
            # Specific domain terms (e.g. gransax, ranni, godrick) receive high weight
            term_weight = 4.0 if len(word) >= 5 else 2.0
            weight = term_weight * (1.0 + (count ** 0.5))
            vector[idx] += weight

        # Normalize to unit vector (L2 norm) for cosine distance compatibility
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [x / norm for x in vector]

        return vector


embedding_service: IEmbeddingService = DeterministicLocalEmbeddingService()
