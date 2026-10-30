"""
checks.py - Consistency and invariant verification stage for pipeline v2.
Validates the LinkedGame artifact for completeness, broken links, and unresolved conflicts.
"""

from pathlib import Path
from src.pipeline.contracts import LinkedGame


def run_checks(game_id: str, data_dir: Path) -> bool:
    """Validate linked/game.json invariants before chunking/loading."""
    raise NotImplementedError("Stage 'check' is not implemented yet.")
