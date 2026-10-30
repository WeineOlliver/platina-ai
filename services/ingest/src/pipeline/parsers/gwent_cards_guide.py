"""
Parser stub for gwent_cards_guide.
"""

from pathlib import Path
from src.pipeline.contracts import GuideParsed


def parse_gwent_cards_guide(file_path: Path, source_id: str = "gwent_cards_guide") -> GuideParsed:
    """Parse a Gwent Card Collector guide HTML snapshot into GuideParsed."""
    # Stub: to be implemented in parsers stage
    raise NotImplementedError("Parser for 'gwent_cards_guide' is not implemented yet.")
