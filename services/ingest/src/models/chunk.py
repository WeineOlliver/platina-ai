from sqlalchemy import Column, String, Text, Boolean, DateTime, func, Computed
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector
from src.config import settings

Base = declarative_base()


class GuideChunkModel(Base):
    """
    SQLAlchemy ORM model mapping to `guide_chunks` table with pgvector support.
    """
    __tablename__ = "guide_chunks"

    id = Column(String(64), primary_key=True)
    game = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    is_missable = Column(Boolean, default=False, index=True)
    source_url = Column(String(500), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    # Insight: Context prefix '<game title> › <DLC ou Base Game> › <section title>' for embedding & search
    context_prefix = Column(String(255), nullable=True, default="")
    # Insight: Vector dimension is dynamically configurable via settings.EMBEDDING_DIMENSIONS
    embedding = Column(Vector(settings.EMBEDDING_DIMENSIONS), nullable=False)
    # Insight: All guides and search queries are processed internally in English, incorporating context prefix
    tsv = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(context_prefix, '') || ' ' || coalesce(title, '') || ' ' || coalesce(content, ''))",
            persisted=True,
        ),
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
