"""
chunk.py - Semantic chunking stage for pipeline v2.
Splits linked guide sections into bounded semantic chunks preserving context prefixes and trophy_id bindings.
"""

from pathlib import Path
from typing import Any, List


def run_chunk(game_id: str, data_dir: Path) -> List[Any]:
    """Generate semantic chunks from linked/game.json."""
    raise NotImplementedError("Stage 'chunk' is not implemented yet.")
