"""
Unit tests for sources.yaml loading and validation rules.
"""

import pytest
from pathlib import Path
from src.pipeline.sources import (
    load_sources,
    validate_sources,
    get_sources_for_game,
    SourceEntry,
)


def test_load_default_sources_yaml():
    sources = load_sources()
    assert len(sources) == 4

    w3_sources = [s for s in sources if s.game_id == "the-witcher-3-wild-hunt"]
    assert len(w3_sources) == 4

    # Validate roles present
    roles = {s.role for s in w3_sources}
    assert roles == {"catalog", "primary_guide", "secondary_guide", "supplement"}

    # Verify that raw snapshot files exist on disk
    for source in w3_sources:
        path = source.resolve_path()
        assert path.exists(), f"Raw snapshot file not found: {path}"


def test_validation_fails_when_zero_catalogs():
    invalid_sources = [
        SourceEntry(
            id="g1_guide",
            game_id="game-1",
            kind="psnprofiles_guide",
            role="primary_guide",
            priority=1,
            url="https://example.com/guide",
            file="data/game-1/raw/guide.html",
        )
    ]
    with pytest.raises(ValueError, match="exactly 1 catalog source is required, but found 0"):
        validate_sources(invalid_sources)


def test_validation_fails_when_multiple_catalogs():
    invalid_sources = [
        SourceEntry(
            id="g1_cat1",
            game_id="game-1",
            kind="psnprofiles_trophy_list",
            role="catalog",
            priority=1,
            url="https://example.com/cat1",
            file="data/game-1/raw/cat1.html",
        ),
        SourceEntry(
            id="g1_cat2",
            game_id="game-1",
            kind="psnprofiles_trophy_list",
            role="catalog",
            priority=2,
            url="https://example.com/cat2",
            file="data/game-1/raw/cat2.html",
        ),
        SourceEntry(
            id="g1_guide",
            game_id="game-1",
            kind="psnprofiles_guide",
            role="primary_guide",
            priority=1,
            url="https://example.com/guide",
            file="data/game-1/raw/guide.html",
        ),
    ]
    with pytest.raises(ValueError, match="exactly 1 catalog source is required, but found 2"):
        validate_sources(invalid_sources)


def test_validation_fails_when_zero_primary_guides():
    invalid_sources = [
        SourceEntry(
            id="g1_cat",
            game_id="game-1",
            kind="psnprofiles_trophy_list",
            role="catalog",
            priority=1,
            url="https://example.com/cat",
            file="data/game-1/raw/cat.html",
        ),
        SourceEntry(
            id="g1_sec",
            game_id="game-1",
            kind="powerpyx_guide",
            role="secondary_guide",
            priority=2,
            url="https://example.com/guide",
            file="data/game-1/raw/sec.html",
        ),
    ]
    with pytest.raises(ValueError, match="at least 1 primary_guide source is required, but found 0"):
        validate_sources(invalid_sources)


def test_get_sources_for_game_sorts_by_priority():
    sources = get_sources_for_game("the-witcher-3-wild-hunt")
    priorities = [s.priority for s in sources]
    assert priorities == sorted(priorities)
