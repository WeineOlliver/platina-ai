import pytest
from pathlib import Path
from src.services.gwent_chunker import chunk_gwent_guide

SNAPSHOT_PATH = Path(__file__).resolve().parent / "golden" / "snapshots" / "gwent_cards_witcher3.html"
TROPHY_ID = "the-witcher-3-wild-hunt-card-collector"
GAME_ID = "the-witcher-3-wild-hunt"


def test_chunk_gwent_guide_parses_snapshot_and_preserves_structure():
    assert SNAPSHOT_PATH.exists(), f"Snapshot not found at {SNAPSHOT_PATH}"
    html_content = SNAPSHOT_PATH.read_text(encoding="utf-8")

    chunks = chunk_gwent_guide(
        html_content=html_content,
        game_id=GAME_ID,
        card_collector_trophy_id=TROPHY_ID,
    )

    assert len(chunks) > 30, f"Expected dozens of atomic chunks, got {len(chunks)}"

    # Insight: Card Collector links Preparation and Step 1..N; mechanics and general intro stay unlinked
    linked_chunks = [c for c in chunks if c.trophy_id is not None]
    unlinked_chunks = [c for c in chunks if c.trophy_id is None]

    assert len(linked_chunks) > 20, "Expected preparation and steps to be linked"
    assert len(unlinked_chunks) > 0, "Expected intro and mechanics chunks to have trophy_id = None"

    for c in linked_chunks:
        assert c.trophy_id == TROPHY_ID, f"Linked chunk {c.title} has wrong trophy_id"
        assert c.metadata.get("trophy_id") == TROPHY_ID
        assert "Card Collector" in c.context_prefix

    for c in unlinked_chunks:
        assert c.trophy_id is None
        assert "Card Collector" not in c.context_prefix

    # Context prefix regions covered by Card Collector steps
    regions = {c.context_prefix.split(" › ")[-1] for c in linked_chunks}
    expected_regions = {"White Orchard", "Vizima", "Velen", "Novigrad", "Skellige", "High Stakes", "Preparation"}
    assert expected_regions.issubset(regions), f"Missing regions in context prefixes: {expected_regions - regions}"

    # Preserves (MISSABLE!) tags and sets is_missable flag
    missable_chunks = [c for c in chunks if c.is_missable]
    assert len(missable_chunks) >= 4, f"Expected multiple missable chunks, got {len(missable_chunks)}"
    missable_tagged = [c for c in chunks if "(MISSABLE!)" in c.content or "(MISSABLE!)" in c.title]
    assert len(missable_tagged) >= 4, "Explicit (MISSABLE!) tags must be preserved in text"

    # Specific missable case: Dandelion from A Matter of Life and Death
    dandelion_chunks = [c for c in chunks if "dandelion" in c.content.lower()]
    assert dandelion_chunks, "Dandelion card chunk not found"
    assert any("matter of life and death" in c.content.lower() for c in dandelion_chunks)
    assert any(c.is_missable for c in dandelion_chunks)

    # Specific vendor case: Quartermaster in Crow's Perch selling Cynthia / Decoy intact
    qm_chunks = [c for c in chunks if "quartermaster" in c.content.lower() and "crow's perch" in c.content.lower()]
    assert qm_chunks, "Quartermaster in Crow's Perch chunk not found"
    qm_content = " ".join(c.content for c in qm_chunks)
    assert "cynthia" in qm_content.lower()
    assert "decoy" in qm_content.lower()

    # Specific total card count preserved
    overview_chunks = [c for c in chunks if "195" in c.content]
    assert overview_chunks, "Total card count chunk (195 cards) not found"
