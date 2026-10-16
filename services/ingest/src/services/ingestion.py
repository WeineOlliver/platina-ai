from typing import List, Dict, Any
from src.schemas.chunk import DocumentChunk
from src.models.chunk import GuideChunkModel
from src.services.embedding import embedding_service
from src.database import get_db_session


class IngestionRepository:
    """
    Manages vectorization and batch storage of trophy guide chunks in pgvector.
    """

    async def ingest_chunks(self, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        if not chunks:
            return {"inserted_count": 0}

        # 1. Extract texts to compute embeddings in batch
        texts_to_embed = [f"{c.title}\n{c.content}" for c in chunks]
        embeddings = await embedding_service.embed_texts(texts_to_embed)

        # 2. Persist in PostgreSQL via atomic transaction
        async with get_db_session() as session:
            for chunk, emb in zip(chunks, embeddings):
                # Upsert record (merge updates existing chunks if re-indexed)
                record = GuideChunkModel(
                    id=chunk.chunk_id,
                    game=chunk.game,
                    title=chunk.title,
                    content=chunk.content,
                    is_missable=chunk.is_missable,
                    source_url=chunk.metadata.get("source_url", ""),
                    metadata_=chunk.metadata,
                    embedding=emb,
                )
                await session.merge(record)

        return {
            "status": "success",
            "inserted_count": len(chunks),
            "game": chunks[0].game if chunks else "",
        }

    async def reindex_game(self, game: str, chunks: List[DocumentChunk]) -> Dict[str, Any]:
        """
        Atomically purges stale chunks for a specific game and re-indexes
        the new guide chunks in a single ACID transaction.
        """
        from sqlalchemy import delete

        texts_to_embed = [f"{c.title}\n{c.content}" for c in chunks]
        embeddings = await embedding_service.embed_texts(texts_to_embed) if chunks else []

        async with get_db_session() as session:
            # 1. Purge existing chunks for the game
            stmt = delete(GuideChunkModel).where(GuideChunkModel.game.ilike(game.strip()))
            result = await session.execute(stmt)
            deleted_count = result.rowcount

            # 2. Insert new chunks
            for chunk, emb in zip(chunks, embeddings):
                record = GuideChunkModel(
                    id=chunk.chunk_id,
                    game=chunk.game,
                    title=chunk.title,
                    content=chunk.content,
                    is_missable=chunk.is_missable,
                    source_url=chunk.metadata.get("source_url", ""),
                    metadata_=chunk.metadata,
                    embedding=emb,
                )
                session.add(record)

        return {
            "status": "reindexed",
            "game": game,
            "deleted_count": deleted_count,
            "reindexed_count": len(chunks),
        }


ingestion_repo = IngestionRepository()
