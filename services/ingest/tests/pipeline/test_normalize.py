"""
Unit tests for canonical name normalization and deterministic trophy ID generation.
"""

import pytest
from src.pipeline.normalize import normalize_name, slugify, generate_trophy_id


def test_normalize_when_its_many_against_one():
    # Test case from spec: "When It’s Many Against One…"
    raw = "When It’s Many Against One…"
    expected = "when it's many against one..."
    assert normalize_name(raw) == expected


def test_normalize_cant_touch_this():
    # Test case from spec: "Can’t Touch This!"
    raw = "Can’t Touch This!"
    expected = "can't touch this!"
    assert normalize_name(raw) == expected


def test_normalize_crows_perch():
    # Test case from spec: "Crow’s Perch"
    raw = "Crow’s Perch"
    expected = "crow's perch"
    assert normalize_name(raw) == expected


def test_normalize_typographical_quotes_and_spaces():
    raw = "  “Double   Quotes”  and  ‘Single   Quotes’ …  "
    expected = '"double quotes" and \'single quotes\' ...'
    assert normalize_name(raw) == expected


def test_normalize_empty_and_whitespace():
    assert normalize_name("") == ""
    assert normalize_name("   ") == ""
    assert normalize_name(None) == ""


def test_slugify():
    assert slugify("When It's Many Against One...") == "when-its-many-against-one"
    assert slugify("Can't Touch This!") == "cant-touch-this"
    assert slugify("Crow's Perch") == "crows-perch"
    assert slugify("  Multiple   --  Spaces  ") == "multiple-spaces"


def test_generate_trophy_id_deterministic_and_stable():
    game_id = "the-witcher-3-wild-hunt"
    assert (
        generate_trophy_id(game_id, "When It’s Many Against One…")
        == "the-witcher-3-wild-hunt-when-its-many-against-one"
    )
    assert (
        generate_trophy_id(game_id, "Can’t Touch This!")
        == "the-witcher-3-wild-hunt-cant-touch-this"
    )
    assert (
        generate_trophy_id(game_id, "Crow’s Perch")
        == "the-witcher-3-wild-hunt-crows-perch"
    )
    assert (
        generate_trophy_id(game_id, "Card Collector")
        == "the-witcher-3-wild-hunt-card-collector"
    )
    assert (
        generate_trophy_id(game_id, "Power Overwhelming")
        == "the-witcher-3-wild-hunt-power-overwhelming"
    )
