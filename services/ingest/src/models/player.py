from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import relationship
from src.models.chunk import Base


class PlayerModel(Base):
    """
    SQLAlchemy ORM model for players.
    """
    __tablename__ = "players"

    id = Column(String(64), primary_key=True)
    psn_id = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    games = relationship("PlayerGameModel", back_populates="player", cascade="all, delete-orphan")


class PlayerGameModel(Base):
    """
    SQLAlchemy ORM model for games tracked by a player.
    """
    __tablename__ = "player_games"

    id = Column(String(64), primary_key=True)
    player_id = Column(String(64), ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    game_title = Column(String(100), nullable=False)
    platform = Column(String(20), default="PS5")
    total_trophies = Column(Integer, default=0)
    unlocked_trophies = Column(Integer, default=0)
    platinum_status = Column(String(20), default="in_progress")
    last_synced_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "game_title", "platform", name="uq_player_game_platform"),
    )

    player = relationship("PlayerModel", back_populates="games")
    trophies = relationship("PlayerTrophyModel", back_populates="game", cascade="all, delete-orphan")


class PlayerTrophyModel(Base):
    """
    SQLAlchemy ORM model for individual trophy states.
    """
    __tablename__ = "player_trophies"

    id = Column(String(64), primary_key=True)
    player_game_id = Column(String(64), ForeignKey("player_games.id", ondelete="CASCADE"), nullable=False, index=True)
    # Insight: Canonical catalog trophy foreign key linking player state to canonical trophy
    trophy_id = Column(String(128), ForeignKey("trophies.id", ondelete="SET NULL"), nullable=True, index=True)
    trophy_name = Column(String(255), nullable=False)
    trophy_type = Column(String(20), nullable=False)
    trophy_category = Column(String(32), default="standard", nullable=False, index=True)
    is_missable = Column(Boolean, default=False, index=True)
    is_unlocked = Column(Boolean, default=False, index=True)
    unlocked_at = Column(DateTime(timezone=True), nullable=True)
    chapter_or_location = Column(String(255), nullable=True)

    __table_args__ = (
        UniqueConstraint("player_game_id", "trophy_name", name="uq_game_trophy"),
    )

    game = relationship("PlayerGameModel", back_populates="trophies")
