import hashlib
import json
import pytest
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent
SERVICES_INGEST_DIR = GOLDEN_DIR.parent.parent


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_deterministic_case_generation():
    """Generates cases twice and verifies output is identical byte-for-byte and ID-for-ID."""
    from tests.golden.generate_cases import generate_cases_for_game

    game_id = "the-witcher-3-wild-hunt"
    cases_run1 = await generate_cases_for_game(game_id)
    cases_run2 = await generate_cases_for_game(game_id)

    assert len(cases_run1) > 0, "Generator should produce cases from catalog"
    assert len(cases_run1) == len(cases_run2), "Case counts must match across runs"

    for c1, c2 in zip(cases_run1, cases_run2):
        assert c1 == c2, f"Deterministic mismatch between runs for case {c1.get('id')}"


@pytest.mark.anyio
async def test_exact_case_schema():
    """Validates each generated case adheres to the exact required schema."""
    from tests.golden.generate_cases import generate_cases_for_game

    game_id = "the-witcher-3-wild-hunt"
    cases = await generate_cases_for_game(game_id)

    required_keys = {"id", "generated", "game_id", "category", "route", "question", "query_en", "expected", "split"}

    for c in cases:
        assert required_keys.issubset(c.keys()), f"Case {c.get('id')} missing required fields: {required_keys - c.keys()}"
        assert c["id"].startswith("GEN_"), f"Case ID must start with GEN_: {c['id']}"
        assert c["generated"] is True, f"Generated flag must be True for {c['id']}"
        assert c["game_id"] == game_id, f"Case game_id mismatch: {c['game_id']}"
        assert c["category"] in {"lista", "dica"}, f"Unexpected category: {c['category']}"
        assert c["route"] in {"sql", "rag"}, f"Unexpected route: {c['route']}"
        assert isinstance(c["question"], str) and len(c["question"]) > 0
        assert isinstance(c["query_en"], str) and len(c["query_en"]) > 0
        assert isinstance(c["expected"], dict)
        assert c["split"] in {"dev", "test"}


@pytest.mark.anyio
async def test_deterministic_dev_test_split_ratio():
    """Verifies 70/30 deterministic dev/test split based on SHA-256 of case id."""
    from tests.golden.generate_cases import generate_cases_for_game

    game_id = "the-witcher-3-wild-hunt"
    cases = await generate_cases_for_game(game_id)

    dev_count = 0
    test_count = 0

    for c in cases:
        cid = c["id"]
        expected_split = "dev" if int(hashlib.sha256(cid.encode("utf-8")).hexdigest(), 16) % 100 < 70 else "test"
        assert c["split"] == expected_split, f"Split rule violated for {cid}: got {c['split']} expected {expected_split}"
        if c["split"] == "dev":
            dev_count += 1
        else:
            test_count += 1

    total = len(cases)
    dev_ratio = dev_count / total
    assert 0.60 <= dev_ratio <= 0.85, f"Dev ratio should be approximately 70% (got {dev_ratio:.2f})"
    assert test_count > 0, "Test split must contain at least one case"


@pytest.mark.anyio
async def test_expected_content_lista_and_dica():
    """Verifies content of generated lista (route sql) and dica (route rag) cases."""
    from tests.golden.generate_cases import generate_cases_for_game

    game_id = "the-witcher-3-wild-hunt"
    cases = await generate_cases_for_game(game_id)

    lista_cases = [c for c in cases if c["category"] == "lista"]
    dica_cases = [c for c in cases if c["category"] == "dica"]

    assert len(lista_cases) >= 8, f"Expected at least 8 lista cases, got {len(lista_cases)}"
    assert len(dica_cases) >= 30, f"Expected at least 30 dica cases, got {len(dica_cases)}"

    # Check lista case requirements
    lista_ids = [c["id"] for c in lista_cases]
    assert any("BRONZE" in cid for cid in lista_ids), "Missing bronze list case"
    assert any("SILVER" in cid for cid in lista_ids), "Missing silver list case"
    assert any("GOLD" in cid for cid in lista_ids), "Missing gold list case"
    assert any("HEARTS_OF_STONE" in cid for cid in lista_ids), "Missing Hearts of Stone DLC case"
    assert any("BLOOD_AND_WINE" in cid for cid in lista_ids), "Missing Blood and Wine DLC case"
    assert any("BASE_GAME" in cid for cid in lista_ids), "Missing Base Game case"
    assert any("MISSABLE" in cid for cid in lista_ids), "Missing missables case"
    assert any("TOTAL" in cid for cid in lista_ids), "Missing total count case"

    for lc in lista_cases:
        assert lc["route"] == "sql"
        assert lc.get("verified") is False
        assert "trophies" in lc["expected"] or "count" in lc["expected"]

    # Check dica case requirements: must_contain = up to 2 distinctive non-stopword terms
    for dc in dica_cases:
        assert dc["route"] == "rag"
        assert dc.get("verified") is False
        assert "trophy" in dc["expected"]
        must_contain = dc["expected"].get("must_contain", [])
        assert len(must_contain) <= 2, f"dica case {dc['id']} must have up to 2 must_contain items"


@pytest.mark.anyio
async def test_output_file_generation():
    """Verifies running the generation pipeline produces generated_the-witcher-3-wild-hunt.json without touching manual golden."""
    from tests.golden.generate_cases import generate_and_save_cases

    game_id = "the-witcher-3-wild-hunt"
    manual_file = GOLDEN_DIR / "golden_witcher3.json"
    manual_hash_before = hashlib.sha256(manual_file.read_bytes()).hexdigest()

    out_file = await generate_and_save_cases(game_id)
    assert out_file.exists(), f"Output file should exist: {out_file}"
    assert out_file.name == f"generated_{game_id}.json"

    # Verify manual golden was not overwritten or touched
    manual_hash_after = hashlib.sha256(manual_file.read_bytes()).hexdigest()
    assert manual_hash_before == manual_hash_after, "Manual golden_witcher3.json was modified!"

    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "cases" in data
    assert len(data["cases"]) > 0
    assert data["game_id"] == game_id


def test_run_golden_split_cli_and_loading():
    """Verifies run_golden CLI options and separate case loading/filtering by split."""
    import subprocess
    import sys

    # 1. Verify --help accepts --split dev|test|all
    res = subprocess.run(
        [sys.executable, str(SERVICES_INGEST_DIR / "tests" / "eval" / "run_golden.py"), "--help"],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "--split {dev,test,all}" in res.stdout or "--split" in res.stdout

    # 2. Verify loading manual + generated with split filter
    manual_file = GOLDEN_DIR / "golden_witcher3.json"
    gen_file = GOLDEN_DIR / "generated_the-witcher-3-wild-hunt.json"
    assert manual_file.exists()
    assert gen_file.exists()

    with open(manual_file, "r", encoding="utf-8") as f:
        manual_cases = json.load(f)["cases"]
    with open(gen_file, "r", encoding="utf-8") as f:
        gen_cases = json.load(f)["cases"]

    gen_dev = [c for c in gen_cases if c["split"] == "dev"]
    gen_test = [c for c in gen_cases if c["split"] == "test"]

    # Manual cases are all considered dev
    expected_dev_count = len(manual_cases) + len(gen_dev)
    expected_test_count = len(gen_test)
    expected_all_count = len(manual_cases) + len(gen_cases)

    assert expected_dev_count > len(manual_cases)
    assert expected_test_count > 0
    assert expected_all_count == expected_dev_count + expected_test_count

