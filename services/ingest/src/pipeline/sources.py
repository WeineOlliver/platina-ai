"""
sources.py - Sources registry loader and validation for pipeline v2.
Validates that every registered game has exactly 1 catalog and at least 1 primary_guide.
"""

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field
import yaml

SourceKind = Literal[
    "psnprofiles_trophy_list",
    "psnprofiles_guide",
    "powerpyx_guide",
    "gwent_cards_guide",
]

SourceRole = Literal[
    "catalog",
    "primary_guide",
    "secondary_guide",
    "supplement",
]


class SourceEntry(BaseModel):
    id: str
    game_id: str
    kind: SourceKind
    role: SourceRole
    priority: int
    url: str
    file: str

    def resolve_path(self, base_dir: Optional[Path] = None) -> Path:
        """Resolve snapshot file path relative to services/ingest base directory."""
        if base_dir is None:
            # Default base dir is services/ingest
            base_dir = Path(__file__).resolve().parent.parent.parent
        return base_dir / self.file


def get_default_sources_yaml_path() -> Path:
    """Return default path to sources.yaml in services/ingest/sources.yaml."""
    return Path(__file__).resolve().parent.parent.parent / "sources.yaml"


def validate_sources(sources: List[SourceEntry]) -> None:
    """
    Enforces pipeline v2 integrity rules:
    - Every registered game must have exactly 1 catalog source.
    - Every registered game must have at least 1 primary_guide source.
    Raises ValueError with a clear explanation if violated.
    """
    by_game: Dict[str, List[SourceEntry]] = defaultdict(list)
    for source in sources:
        by_game[source.game_id].append(source)

    for game_id, game_sources in by_game.items():
        catalog_count = sum(1 for s in game_sources if s.role == "catalog")
        primary_count = sum(1 for s in game_sources if s.role == "primary_guide")

        if catalog_count != 1:
            raise ValueError(
                f"Validation error for game '{game_id}': exactly 1 catalog source is required, "
                f"but found {catalog_count}."
            )

        if primary_count < 1:
            raise ValueError(
                f"Validation error for game '{game_id}': at least 1 primary_guide source is required, "
                f"but found {primary_count}."
            )


def load_sources(yaml_path: Optional[Path] = None) -> List[SourceEntry]:
    """
    Load and validate sources from sources.yaml.
    """
    if yaml_path is None:
        yaml_path = get_default_sources_yaml_path()

    if not yaml_path.exists():
        raise FileNotFoundError(f"Sources registry not found at: {yaml_path}")

    raw_data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    raw_sources = raw_data.get("sources", [])

    entries: List[SourceEntry] = []
    for item in raw_sources:
        entries.append(SourceEntry(**item))

    validate_sources(entries)
    return entries


def get_sources_for_game(game_id: str, yaml_path: Optional[Path] = None) -> List[SourceEntry]:
    """
    Retrieve and validate sources for a specific game_id, ordered by role priority.
    """
    all_sources = load_sources(yaml_path)
    game_sources = [s for s in all_sources if s.game_id == game_id]
    if not game_sources:
        raise ValueError(f"No sources registered for game_id: '{game_id}'.")
    return sorted(game_sources, key=lambda s: s.priority)
