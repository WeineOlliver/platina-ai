from sqlalchemy import Column, String, Text, Integer, Numeric, Boolean, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from src.models.chunk import Base


class GameModel(Base):
    """
    SQLAlchemy ORM model for canonical games catalog.
    """
    __tablename__ = "games"

    id = Column(String(100), primary_key=True)  # slug PK (e.g. 'the-witcher-3-wild-hunt')
    title = Column(String(255), nullable=False)
    np_communication_id = Column(String(64), nullable=True)
    aliases = Column(ARRAY(Text), default=list)
    difficulty = Column(Numeric, nullable=True)
    hours = Column(Integer, nullable=True)
    playthroughs = Column(Integer, nullable=True)
    metadata_source = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    trophies = relationship("TrophyModel", back_populates="game", cascade="all, delete-orphan")


class TrophyModel(Base):
    """
    SQLAlchemy ORM model for canonical trophies catalog.
    """
    __tablename__ = "trophies"

    id = Column(String(128), primary_key=True)
    game_id = Column(String(100), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True)
    psn_trophy_id = Column(Integer, nullable=True)
    name = Column(String(255), nullable=False)
    type = Column(String(20), nullable=False)
    description = Column(Text, nullable=True)
    dlc = Column(String(100), nullable=True)  # null = base game
    location = Column(ARRAY(Text), nullable=True)
    missable = Column(Boolean, default=False, nullable=False, index=True)
    missable_sources = Column(ARRAY(Text), default=list)
    aliases = Column(ARRAY(Text), default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("game_id", "name", name="uq_trophy_game_name"),
    )

    game = relationship("GameModel", back_populates="trophies")
