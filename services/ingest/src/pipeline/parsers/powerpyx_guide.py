"""
Parser stub for powerpyx_guide.
"""

from pathlib import Path
from src.pipeline.contracts import GuideParsed


def parse_powerpyx_guide(file_path: Path, source_id: str = "powerpyx_guide") -> GuideParsed:
    """Parse a PowerPyx guide HTML snapshot into GuideParsed."""
    # Stub: to be implemented in parsers stage
    raise NotImplementedError("Parser for 'powerpyx_guide' is not implemented yet.")
