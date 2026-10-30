"""
Unit tests for pipeline v2 Pydantic contracts and JSON roundtrip serialization.
"""

import json
import pytest
from pydantic import ValidationError
from src.pipeline.contracts import (
    TrophyParsed,
    TrophyListParsed,
    GuideOverview,
    GuideMissable,
    GuideSection,
    GuideParsed,
    GameInfo,
    LinkedTrophy,
    LinkedSection,
    LinkedConflict,
    LinkedUnlinked,
    LinkedGame,
    compute_trophy_id,
)


def test_trophy_list_parsed_roundtrip():
    trophy = TrophyParsed(
        name="When It’s Many Against One…",
        type="bronze",
        description="Defeat all Iris von Everec's Nightmares simultaneously.",
        group="Hearts of Stone",
        psn_trophy_id=60,
    )
    trophy_list = TrophyListParsed(
        game_title="The Witcher 3: Wild Hunt",
        np_communication_id="NPWR20111_00",
        trophies=[trophy],
    )

    data = json.loads(trophy_list.model_dump_json())
    restored = TrophyListParsed.model_validate(data)

    assert restored.game_title == "The Witcher 3: Wild Hunt"
    assert restored.np_communication_id == "NPWR20111_00"
    assert len(restored.trophies) == 1
    assert restored.trophies[0].name == "When It’s Many Against One…"
    assert restored.trophies[0].group == "Hearts of Stone"
    assert restored.trophies[0].psn_trophy_id == 60


def test_guide_parsed_roundtrip():
    guide = GuideParsed(
        source_id="psnprofiles_guide",
        overview=GuideOverview(difficulty="7/10", hours="110h", playthroughs="2"),
        missables=[GuideMissable(trophy_name="Full Crew"), GuideMissable(trophy_name="Card Collector")],
        locations={"Novigrad": ["Gwent Master", "Assassin of Kings"], "Skellige": ["Woodland Spirit"]},
        sections=[
            GuideSection(
                order=1,
                kind="roadmap",
                title="Roadmap & Overview",
                text="Step by step roadmap.",
            ),
            GuideSection(
                order=2,
                kind="trophy",
                title="Full Crew Guide",
                trophy_name="Full Crew",
                text="Recruit all allies to Kaer Morhen.",
                parent_title="Missable Trophies",
            ),
        ],
    )

    data = json.loads(guide.model_dump_json())
    restored = GuideParsed.model_validate(data)

    assert restored.source_id == "psnprofiles_guide"
    assert restored.overview.difficulty == "7/10"
    assert len(restored.missables) == 2
    assert "Novigrad" in restored.locations
    assert len(restored.sections) == 2
    assert restored.sections[1].kind == "trophy"
    assert restored.sections[1].trophy_name == "Full Crew"


def test_guide_section_kind_validation():
    # Valid kinds: trophy, roadmap, collectible_group, general
    section = GuideSection(
        order=1,
        kind="collectible_group",
        title="Gwent Cards",
        text="Card checklist.",
    )
    assert section.kind == "collectible_group"

    with pytest.raises(ValidationError):
        GuideSection(
            order=2,
            kind="invalid_kind",  # pyright: ignore[reportArgumentType]
            title="Bad",
            text="Bad",
        )


def test_linked_game_roundtrip_with_deterministic_ids():
    game_id = "the-witcher-3-wild-hunt"
    t_name = "When It’s Many Against One…"
    trophy_id = compute_trophy_id(game_id, t_name)
    assert trophy_id == "the-witcher-3-wild-hunt-when-its-many-against-one"

    linked = LinkedGame(
        game=GameInfo(id=game_id, title="The Witcher 3: Wild Hunt"),
        trophies=[
            LinkedTrophy(
                trophy_id=trophy_id,
                name=t_name,
                type="bronze",
                description="Defeat all Iris von Everec's Nightmares.",
                group="Hearts of Stone",
                psn_trophy_id=60,
                aliases=[],
                missable_sources=["powerpyx_guide"],
            )
        ],
        sections=[
            LinkedSection(
                order=1,
                kind="trophy",
                title="When It’s Many Against One… Walkthrough",
                trophy_name=t_name,
                trophy_id=trophy_id,
                text="Provoke all 6 nightmares with Whirl.",
                source_id="powerpyx_guide",
            )
        ],
        conflicts=[
            LinkedConflict(
                fact="missable_status",
                details={"trophy": t_name, "powerpyx": True, "psnprofiles": False},
            )
        ],
        unlinked=[
            LinkedUnlinked(
                section=GuideSection(
                    order=99,
                    kind="trophy",
                    title="Unknown Secret Trophy",
                    text="Some text",
                ),
                source_id="powerpyx_guide",
                reason="No matching catalog trophy found",
            )
        ],
    )

    data = json.loads(linked.model_dump_json())
    restored = LinkedGame.model_validate(data)

    assert restored.game.id == game_id
    assert len(restored.trophies) == 1
    assert restored.trophies[0].trophy_id == trophy_id
    assert restored.trophies[0].aliases == []
    assert restored.trophies[0].missable_sources == ["powerpyx_guide"]
    assert len(restored.sections) == 1
    assert restored.sections[0].trophy_id == trophy_id
    assert len(restored.conflicts) == 1
    assert len(restored.unlinked) == 1
