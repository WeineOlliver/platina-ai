"""
link.py - Linking stage for pipeline v2.
Merges parsed sources into a unified LinkedGame artifact with deterministic trophy IDs.
"""

from pathlib import Path
from src.pipeline.contracts import LinkedGame


def run_link(game_id: str, data_dir: Path) -> LinkedGame:
    """Read parsed/*.json for the game and generate linked/game.json."""
    raise NotImplementedError("Stage 'link' is not implemented yet.")
