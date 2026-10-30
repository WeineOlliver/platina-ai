"""
Parsers registry and dispatcher for pipeline v2.
"""

from typing import Any, Callable
from src.pipeline.sources import SourceKind


def get_parser_for_kind(kind: SourceKind) -> Callable[..., Any]:
    """Return the parser callable for the requested source kind."""
    if kind == "psnprofiles_trophy_list":
        from src.pipeline.parsers.psnprofiles_trophy_list import parse_psnprofiles_trophy_list
        return parse_psnprofiles_trophy_list
    elif kind == "psnprofiles_guide":
        from src.pipeline.parsers.psnprofiles_guide import parse_psnprofiles_guide
        return parse_psnprofiles_guide
    elif kind == "powerpyx_guide":
        from src.pipeline.parsers.powerpyx_guide import parse_powerpyx_guide
        return parse_powerpyx_guide
    elif kind == "gwent_cards_guide":
        from src.pipeline.parsers.gwent_cards_guide import parse_gwent_cards_guide
        return parse_gwent_cards_guide
    raise ValueError(f"Unknown source kind: {kind}")
