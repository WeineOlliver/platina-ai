#!/usr/bin/env python3
"""
services/ingest/tests/golden/generate_cases.py

Synthetic Golden Case Generator from Canonical Catalog & Entity Linking.
Produces deterministic exact-answer golden cases without LLM:
- lista (route sql): type (bronze, silver, gold), DLC (Hearts of Stone, Blood and Wine, Base Game), missables, total count.
- dica (route rag): trophies with linked guide chunks and distinctive must_contain terms.
Deterministic 70/30 dev/test split via SHA-256 of case id.
"""

import argparse
import asyncio
import datetime
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from collections import Counter

# Ensure services/ingest is on sys.path
SERVICES_INGEST_DIR = Path(__file__).resolve().parent.parent.parent
if str(SERVICES_INGEST_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_INGEST_DIR))

from sqlalchemy import select
from src.database import get_db_session
from src.models.catalog import GameModel, TrophyModel
from src.models.chunk import GuideChunkModel
from src.services.entity_linker import get_canonical_game_id

GOLDEN_DIR = SERVICES_INGEST_DIR / "tests" / "golden"

# Insight: Distinctive term extraction ignores frequent generic words and noise
STOPWORDS = {
    "about", "above", "after", "again", "against", "all", "also", "and", "any", "are", "because",
    "been", "before", "being", "below", "between", "both", "but", "by", "can", "cannot", "could",
    "did", "does", "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has",
    "have", "having", "here", "how", "into", "itself", "just", "more", "most", "only", "other",
    "our", "out", "over", "same", "should", "some", "such", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "too", "under", "until", "very",
    "was", "were", "what", "when", "where", "which", "while", "who", "whom", "why", "will", "with",
    "would", "you", "your", "guide", "video", "trophy", "witcher", "game", "part", "need", "make",
    "sure", "take", "well", "much", "many", "come", "find", "first", "even", "trophies", "unlock",
    "unlocked", "obtain", "obtained", "player", "players", "story", "quest", "quests", "mission",
    "missions", "level", "press", "button", "screen", "menu", "complete", "completed", "area",
    "location", "place", "found", "around", "follow", "steps", "simply", "easily", "instead",
    "another", "together", "enough", "already", "different", "important", "remember", "note",
    "time", "times", "good", "best", "great", "every", "going", "right", "left",
    "congratulations", "hellbornhunter", "recommendend", "inivtation", "shirker", "patch", "works",
    "credit", "powerpyx", "psnprofiles", "refer", "information", "described", "achieve", "achieved",
    "order", "along", "beforehand", "attempt", "quick", "breakdown", "either", "without", "between",
    "something", "anything", "nothing", "everything", "someone", "anyone", "using", "used", "uses",
    "allows", "allowing", "allowed", "likely", "unlikely", "especially", "considering", "number",
}


def compute_split(case_id: str) -> str:
    """Deterministic 70/30 dev/test split based on SHA-256 hash of case id."""
    val = int(hashlib.sha256(case_id.encode("utf-8")).hexdigest(), 16) % 100
    return "dev" if val < 70 else "test"


def extract_must_contain_terms(
    trophy_id: str,
    trophy_name: str,
    chunks_content: List[str],
    trophy_ids_by_word: Dict[str, Set[str]],
    total_corpus_counter: Counter,
    catalog_vocab: Set[str],
) -> List[str]:
    """
    Extracts 1 or 2 distinctive terms that appear in this trophy's chunks
    and DO NOT appear in any other trophy's chunks of the same game.
    Requires at least 2 occurrences in corpus or presence in catalog vocabulary.
    Returns empty list if no distinctive term meets criteria.
    """
    full_text = " ".join(chunks_content)
    words = re.findall(r"\b[A-Za-z]{4,}\b", full_text)
    tname_words = set(re.findall(r"\b[A-Za-z]+\b", trophy_name.lower()))

    word_counts = Counter(w.lower() for w in words)
    candidates = []

    for w, count in word_counts.items():
        if w in STOPWORDS:
            continue
        if w in tname_words:
            continue
        # Distinctiveness: must not appear in chunks of other trophies of this game
        other_trophies = trophy_ids_by_word.get(w, set()) - {trophy_id}
        if other_trophies:
            continue
        # Frequency check: at least 2 in corpus or in catalog vocabulary
        corpus_count = total_corpus_counter.get(w, 0)
        if corpus_count < 2 and w not in catalog_vocab:
            continue
        candidates.append((w, count, corpus_count))

    if not candidates:
        return []

    casing_map = {}
    for original_word in words:
        low = original_word.lower()
        if low not in casing_map or (original_word[0].isupper() and not casing_map[low][0].isupper()):
            casing_map[low] = original_word

    candidates.sort(key=lambda item: (-item[1], not casing_map[item[0]][0].isupper(), item[0]))
    return [casing_map[item[0]] for item in candidates[:2]]


async def generate_cases_for_game(game_slug_or_title: str) -> List[Dict[str, Any]]:
    """
    Generates exact-answer cases for the given game without LLM.
    Reads canonical trophies and linked guide chunks from the database.
    """
    clean_id = get_canonical_game_id(game_slug_or_title)

    async with get_db_session() as session:
        game_stmt = select(GameModel).where(
            (GameModel.id == clean_id)
            | (GameModel.id == game_slug_or_title.strip().lower())
            | (GameModel.title.ilike(game_slug_or_title.strip()))
        ).limit(1)
        game = (await session.execute(game_stmt)).scalars().first()
        if not game:
            raise ValueError(f"Game '{game_slug_or_title}' not found in catalog database.")

        trophies_stmt = select(TrophyModel).where(TrophyModel.game_id == game.id).order_by(TrophyModel.id.asc())
        trophies = (await session.execute(trophies_stmt)).scalars().all()

        chunks_stmt = (
            select(GuideChunkModel)
            .where(GuideChunkModel.game_id == game.id, GuideChunkModel.trophy_id.is_not(None))
            .order_by(GuideChunkModel.id.asc())
        )
        chunks = (await session.execute(chunks_stmt)).scalars().all()

    cases: List[Dict[str, Any]] = []

    # 1. SQL LISTA Cases (Exact SQL route from catalog)
    # 1.1 By type (bronze, silver, gold)
    for t_type in ["bronze", "silver", "gold"]:
        matched = sorted([t.name for t in trophies if t.type.lower() == t_type])
        pt_type = {"bronze": "bronze", "silver": "prata", "gold": "ouro"}.get(t_type, t_type)
        cid = f"GEN_LISTA_TYPE_{t_type.upper()}"
        cases.append({
            "id": cid,
            "generated": True,
            "verified": False,
            "game_id": game.id,
            "category": "lista",
            "route": "sql",
            "question": f"Quais troféus de {pt_type} existem em {game.title}?",
            "query_en": f"Which {t_type} trophies exist in {game.title}?",
            "expected": {
                "trophies": matched,
                "count": len(matched),
            },
            "filter": {"type": t_type},
            "split": compute_split(cid),
        })

    # 1.2 By DLC (Hearts of Stone, Blood and Wine, Base Game)
    base_trophies = sorted([t.name for t in trophies if t.dlc is None])
    cid_base = "GEN_LISTA_DLC_BASE_GAME"
    cases.append({
        "id": cid_base,
        "generated": True,
        "verified": False,
        "game_id": game.id,
        "category": "lista",
        "route": "sql",
        "question": f"Quais troféus são do jogo base de {game.title}?",
        "query_en": f"Which trophies are from the base game of {game.title}?",
        "expected": {
            "trophies": base_trophies,
            "count": len(base_trophies),
        },
        "filter": {"dlc": "Base Game"},
        "split": compute_split(cid_base),
    })

    dlc_names = sorted(list(set(t.dlc for t in trophies if t.dlc)))
    for dlc in dlc_names:
        dlc_slug = re.sub(r"[^A-Za-z0-9]+", "_", dlc).strip("_").upper()
        dlc_trophies = sorted([t.name for t in trophies if t.dlc == dlc])
        cid_dlc = f"GEN_LISTA_DLC_{dlc_slug}"
        cases.append({
            "id": cid_dlc,
            "generated": True,
            "verified": False,
            "game_id": game.id,
            "category": "lista",
            "route": "sql",
            "question": f"Quais troféus são da DLC {dlc}?",
            "query_en": f"Which trophies are from the {dlc} DLC?",
            "expected": {
                "trophies": dlc_trophies,
                "count": len(dlc_trophies),
            },
            "filter": {"dlc": dlc},
            "split": compute_split(cid_dlc),
        })

    # 1.3 Missables (list and count)
    missable_trophies = sorted([t.name for t in trophies if t.missable])
    cid_miss = "GEN_LISTA_MISSABLES"
    cases.append({
        "id": cid_miss,
        "generated": True,
        "verified": False,
        "game_id": game.id,
        "category": "lista",
        "route": "sql",
        "question": f"Quais troféus são perdíveis em {game.title}?",
        "query_en": f"Which trophies are missable in {game.title}?",
        "expected": {
            "trophies": missable_trophies,
            "count": len(missable_trophies),
        },
        "filter": {"missable": True},
        "split": compute_split(cid_miss),
    })

    cid_miss_cnt = "GEN_LISTA_MISSABLES_COUNT"
    cases.append({
        "id": cid_miss_cnt,
        "generated": True,
        "verified": False,
        "game_id": game.id,
        "category": "lista",
        "route": "sql",
        "question": f"Quantos troféus perdíveis existem em {game.title}?",
        "query_en": f"How many missable trophies are there in {game.title}?",
        "expected": {
            "count": len(missable_trophies),
        },
        "filter": {"missable": True},
        "split": compute_split(cid_miss_cnt),
    })

    # 1.4 Total count
    cid_total = "GEN_LISTA_TOTAL_COUNT"
    cases.append({
        "id": cid_total,
        "generated": True,
        "verified": False,
        "game_id": game.id,
        "category": "lista",
        "route": "sql",
        "question": f"Quantos troféus existem no total em {game.title}?",
        "query_en": f"How many total trophies are there in {game.title}?",
        "expected": {
            "count": len(trophies),
        },
        "filter": {"total": True},
        "split": compute_split(cid_total),
    })

    # 2. RAG DICA Cases (for trophies that have linked guide_chunks)
    chunks_by_trophy: Dict[str, List[GuideChunkModel]] = {}
    total_corpus_counter: Counter = Counter()
    for c in chunks:
        chunks_by_trophy.setdefault(c.trophy_id, []).append(c)
        for w in re.findall(r"\b[A-Za-z]{4,}\b", c.content or ""):
            total_corpus_counter[w.lower()] += 1

    catalog_vocab: Set[str] = set()
    for t in trophies:
        catalog_vocab.update(w.lower() for w in re.findall(r"\b[A-Za-z]{3,}\b", t.name))
        if t.description:
            catalog_vocab.update(w.lower() for w in re.findall(r"\b[A-Za-z]{3,}\b", t.description))

    trophy_ids_by_word: Dict[str, Set[str]] = {}
    for t_id, linked_chunks in chunks_by_trophy.items():
        text = " ".join(c.content for c in linked_chunks if c.content)
        words = set(w.lower() for w in re.findall(r"\b[A-Za-z]{4,}\b", text))
        for w in words:
            trophy_ids_by_word.setdefault(w, set()).add(t_id)

    trophies_by_id = {t.id: t for t in trophies}
    for t_id, linked_chunks in sorted(chunks_by_trophy.items()):
        trophy = trophies_by_id.get(t_id)
        if not trophy:
            continue

        raw_contents = [c.content for c in linked_chunks if c.content]
        must_contain = extract_must_contain_terms(
            trophy_id=t_id,
            trophy_name=trophy.name,
            chunks_content=raw_contents,
            trophy_ids_by_word=trophy_ids_by_word,
            total_corpus_counter=total_corpus_counter,
            catalog_vocab=catalog_vocab,
        )

        slug_name = re.sub(r"[^A-Za-z0-9]+", "_", trophy.name).strip("_").upper()
        cid = f"GEN_DICA_{slug_name}"

        exp_dict: Dict[str, Any] = {"trophy": trophy.name}
        if must_contain:
            exp_dict["must_contain"] = must_contain

        cases.append({
            "id": cid,
            "generated": True,
            "verified": False,
            "game_id": game.id,
            "category": "dica",
            "route": "rag",
            "question": f"Como pegar o troféu {trophy.name} em {game.title}?",
            "query_en": f"How to get the {trophy.name} trophy?",
            "expected": exp_dict,
            "split": compute_split(cid),
        })

    return cases


async def generate_and_save_cases(game_slug_or_title: str, output_dir: Optional[Path] = None) -> Path:
    """Generates cases and writes them to tests/golden/generated_<game_id>.json."""
    cases = await generate_cases_for_game(game_slug_or_title)
    clean_id = get_canonical_game_id(game_slug_or_title)

    out_dir = output_dir or GOLDEN_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"generated_{clean_id}.json"

    dev_cases = [c for c in cases if c["split"] == "dev"]
    test_cases = [c for c in cases if c["split"] == "test"]

    payload = {
        "game_id": clean_id,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_cases": len(cases),
        "dev_cases": len(dev_cases),
        "test_cases": len(test_cases),
        "cases": cases,
    }

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Synthetic Golden Case Generator from Canonical Catalog")
    parser.add_argument("game_id", help="Canonical game ID or title (e.g. the-witcher-3-wild-hunt)")
    args = parser.parse_args()

    out_file = asyncio.run(generate_and_save_cases(args.game_id))
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[OK] Generated {data['total_cases']} cases for '{data['game_id']}':")
    print(f"     - Dev split:  {data['dev_cases']} cases")
    print(f"     - Test split: {data['test_cases']} cases")
    print(f"[OUTPUT] Saved to: {out_file}")


if __name__ == "__main__":
    main()
