from sqlalchemy import Column, String, Text, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

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
    embedding = Column(Vector(1536), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
