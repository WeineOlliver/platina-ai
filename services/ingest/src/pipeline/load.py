"""
load.py - Database loading stage for pipeline v2.
Loads verified linked game artifacts and semantic chunks into PostgreSQL / pgvector.
"""

from pathlib import Path


def run_load(game_id: str, data_dir: Path) -> None:
    """Load verified artifacts into relational and vector databases."""
    raise NotImplementedError("Stage 'load' is not implemented yet.")
