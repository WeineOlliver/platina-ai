"""
normalize.py - Canonical string normalization and stable deterministic ID generation.
Single source of truth used across pipeline parsing, catalog import, entity linking, and evaluation.
"""

import re
from typing import Optional


def normalize_name(name: Optional[str]) -> str:
    """
    Canonical name normalization:
    - Typographical apostrophes/single quotes (’, ‘, ‚, ‛, ′, `) -> ASCII '
    - Typographical double quotes (“ , ”, „, ‟, ″) -> ASCII "
    - Ellipsis … -> ...
    - Collapses consecutive whitespace and strips ends
    - Unicode casefold for case-insensitive comparison
    """
    if not name:
        return ""
    # Typographical apostrophes / single quotes to ASCII '
    s = re.sub(r"[’‘‚‛′`]", "'", name)
    # Typographical double quotes to ASCII "
    s = re.sub(r"[“”„‟″]", '"', s)
    # Typographical ellipsis … to ...
    s = s.replace("…", "...")
    # Collapse multiple whitespaces and strip boundaries
    s = re.sub(r"\s+", " ", s).strip()
    return s.casefold()


def slugify(text: Optional[str]) -> str:
    """
    Generate deterministic slug:
    - Strips non-alphanumeric, non-hyphen, and non-space characters
    - Replaces whitespace and sequences of hyphens with a single hyphen
    - Lowercase ASCII
    """
    if not text:
        return ""
    # Strip characters that are not word characters, spaces, or hyphens (e.g. apostrophes, commas, exclamation marks)
    clean = re.sub(r"[^\w\s-]", "", text).strip()
    return re.sub(r"[-\s]+", "-", clean).lower()


def generate_trophy_id(game_id: str, trophy_name: str) -> str:
    """
    Deterministic trophy_id = slug(game_id + nome normalizado).
    Stable and immutable across pipeline rebuilds to safeguard player progress references.
    """
    norm = normalize_name(trophy_name)
    trophy_slug = slugify(norm)
    return f"{game_id}-{trophy_slug}"
