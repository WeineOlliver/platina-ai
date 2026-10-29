import hashlib
import re
from typing import List, Optional
from bs4 import BeautifulSoup
from src.schemas.chunk import DocumentChunk

# Insight: Ensure DocumentChunk accepts dynamic entity linking fields
DocumentChunk.model_config["extra"] = "allow"
DocumentChunk.model_rebuild(force=True)

DEFAULT_GAME_ID = "the-witcher-3-wild-hunt"
DEFAULT_TROPHY_ID = "the-witcher-3-wild-hunt-card-collector"
DEFAULT_GAME_TITLE = "The Witcher 3: Wild Hunt"


def _clean_text(node) -> str:
    # Insight: Normalize whitespace while preserving (MISSABLE!) tags and exact casing
    if not node:
        return ""
    text = node.get_text(" ", strip=True) if hasattr(node, "get_text") else str(node)
    return re.sub(r"\s+", " ", text).strip()


def _extract_region(sec_id: str, title: str) -> str:
    s = f"{sec_id} {title}".lower()
    if "white orchard" in s:
        return "White Orchard"
    if "vizima" in s:
        return "Vizima"
    if "velen" in s:
        return "Velen"
    if "novigrad" in s:
        return "Novigrad"
    if "skellige" in s:
        return "Skellige"
    if "finale" in s or "high stakes" in s:
        return "High Stakes"
    if "preparation" in s:
        return "Preparation"
    if "how to play" in s or "mechanics" in s or "introduction to gwent" in s:
        return "Gwent Mechanics"
    return "Overview"


def chunk_gwent_guide(
    html_content: str,
    game_id: str = DEFAULT_GAME_ID,
    card_collector_trophy_id: str = DEFAULT_TROPHY_ID,
    source_url: str = "https://psnprofiles.com/guide/4250-the-witcher-3-wild-hunt-card-collector-guide",
) -> List[DocumentChunk]:
    """
    Parses gwent_cards_witcher3.html into atomic chunks per vendor/NPC, roadmap step,
    and region overview without splitting list boundaries. Links all chunks to Card Collector.
    """
    if not html_content or not html_content.strip():
        return []

    game_title = DEFAULT_GAME_TITLE if "witcher" in game_id.lower() else game_id
    soup = BeautifulSoup(html_content, "html.parser")
    sections = soup.find_all("div", class_="section-holder")

    chunks: List[DocumentChunk] = []
    chunk_idx = 0

    for s in sections:
        sec_id_tag = s.find("div", id=True)
        sec_id = sec_id_tag["id"] if sec_id_tag else ""
        title_el = s.find(["h3", "h2", "h1"])
        sec_title = title_el.get_text(strip=True) if title_el else ""
        region = _extract_region(sec_id, sec_title)

        fr = s.find("div", class_="fr-view")
        if not fr:
            continue

        ols = fr.find_all("ol")
        uls = fr.find_all("ul")

        # 1. Non-list sections (Overview, Finale / High Stakes, Preparation)
        if not ols and not uls:
            text = _clean_text(fr)
            if text:
                chunks.append(_create_chunk(
                    game_title=game_title,
                    game_id=game_id,
                    region=region,
                    sub_title="Overview",
                    content=text,
                    source_url=source_url,
                    trophy_id=card_collector_trophy_id,
                    index=chunk_idx,
                ))
                chunk_idx += 1
            continue

        # 2. Intro / starting deck prose preceding lists
        intro_paras = []
        for child in fr.children:
            if getattr(child, "name", None) in ["h2", "ol", "ul"]:
                break
            txt = _clean_text(child)
            if txt and len(txt) > 30 and "gosunoob" not in txt.lower():
                intro_paras.append(txt)
        if intro_paras:
            intro_text = " ".join(intro_paras)
            chunks.append(_create_chunk(
                game_title=game_title,
                game_id=game_id,
                region=region,
                sub_title="Overview & Intro",
                content=intro_text,
                source_url=source_url,
                trophy_id=card_collector_trophy_id,
                index=chunk_idx,
            ))
            chunk_idx += 1

        # 3. Places of Interest: atomic chunks per vendor / NPC
        for ol in ols:
            for li in ol.find_all("li", recursive=False):
                txt = _clean_text(li)
                if not txt:
                    continue
                vendor = txt.split(".")[0].strip()
                if len(vendor) > 60:
                    vendor = vendor[:60].strip()
                chunks.append(_create_chunk(
                    game_title=game_title,
                    game_id=game_id,
                    region=region,
                    sub_title=vendor,
                    content=txt,
                    source_url=source_url,
                    trophy_id=card_collector_trophy_id,
                    index=chunk_idx,
                ))
                chunk_idx += 1

        # 4. Roadmap: atomic chunks per roadmap step preserving (MISSABLE!) tags
        for ul in uls:
            for li in ul.find_all("li", recursive=False):
                txt = _clean_text(li)
                if not txt:
                    continue
                step_m = re.match(r"^(STEP\s+\d+[^.]+)", txt, re.IGNORECASE)
                step_name = step_m.group(1).strip() if step_m else "Roadmap Step"
                chunks.append(_create_chunk(
                    game_title=game_title,
                    game_id=game_id,
                    region=region,
                    sub_title=step_name,
                    content=txt,
                    source_url=source_url,
                    trophy_id=card_collector_trophy_id,
                    index=chunk_idx,
                ))
                chunk_idx += 1

    return chunks


def _create_chunk(
    game_title: str,
    game_id: str,
    region: str,
    sub_title: str,
    content: str,
    source_url: str,
    trophy_id: str,
    index: int,
) -> DocumentChunk:
    title = f"Card Collector — {region}: {sub_title}"
    prefix = f"{game_title} › Base Game › Card Collector › {region}"
    is_missable = "(MISSABLE!)" in content or "missable" in content.lower() or "(missable!)" in title.lower()

    id_raw = f"{game_id}:gwent:{title}:{index}:{content[:40]}"
    chunk_id = hashlib.sha256(id_raw.encode("utf-8")).hexdigest()[:24]

    chunk = DocumentChunk(
        chunk_id=chunk_id,
        game=game_title,
        title=title,
        content=content,
        is_missable=is_missable,
        metadata={
            "source_url": source_url,
            "region": region,
            "trophy_id": trophy_id,
            "game_id": game_id,
            "chunk_index": index,
            "char_length": len(content),
        },
    )
    chunk.trophy_id = trophy_id
    chunk.context_prefix = prefix
    return chunk
