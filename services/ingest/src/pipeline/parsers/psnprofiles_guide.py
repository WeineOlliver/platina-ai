"""
Parser stub for psnprofiles_guide.
"""

from pathlib import Path
from src.pipeline.contracts import GuideParsed


def parse_psnprofiles_guide(file_path: Path, source_id: str = "psnprofiles_guide") -> GuideParsed:
    """Parse a PSNProfiles trophy guide HTML snapshot into GuideParsed."""
    # Stub: to be implemented in parsers stage
    raise NotImplementedError("Parser for 'psnprofiles_guide' is not implemented yet.")
