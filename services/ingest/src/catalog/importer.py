import re
import sys
from decimal import Decimal
from typing import Optional, Dict, Any, List, Set
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import select

from src.database import get_db_session
from src.models.catalog import GameModel, TrophyModel


def slugify(text: str) -> str:
    # Deterministic slug for canonical primary keys
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", slug)[:100]


def extract_game_title(soup: BeautifulSoup, default_title: str) -> str:
    # Extract canonical game title from title bar, h1-h3, or document title
    for el in soup.find_all(["div", "h1", "h2", "h3"], class_="title"):
        txt = el.get_text(strip=True)
        if txt and "trophies" in txt.lower():
            clean = re.sub(r"\s+Trophies.*$", "", txt, flags=re.IGNORECASE).strip()
            if clean:
                return clean
    if soup.title and soup.title.string:
        clean = soup.title.string.strip()
        clean = re.sub(r"\s+Trophies.*$", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s+•.*$", "", clean).strip()
        if clean:
            return clean
    return default_title


def parse_trophies_html(html_content: str, default_title: str = "Unknown Game") -> Dict[str, Any]:
    # Parse PSNProfiles trophies list, extracting Base Game and DLC groupings
    soup = BeautifulSoup(html_content, "html.parser")
    title = extract_game_title(soup, default_title)

    trophies: List[Dict[str, Any]] = []

    # PSNProfiles wraps DLCs/Base Game in div.box containers with span.title headers
    boxes = soup.find_all("div", class_="box")
    candidate_sections = []

    for b in boxes:
        title_span = b.find("span", class_="title")
        sec_title = title_span.text.strip() if title_span else ""
        if not sec_title:
            prev = b.find_previous(["h2", "h3", "h4"])
            if prev:
                sec_title = prev.text.strip()
        # Verify box contains trophy rows
        has_trophies = any("/trophy/" in a.get("href", "") for a in b.find_all("a", class_="title"))
        if has_trophies:
            candidate_sections.append((sec_title, b))

    # Fallback to entire document if no structured boxes found
    if not candidate_sections:
        candidate_sections = [("", soup)]

    for sec_title, container in candidate_sections:
        # None for Base Game; DLC name for DLC expansions
        dlc = None if (not sec_title or "base game" in sec_title.lower()) else sec_title

        rows = container.find_all("tr")
        for r in rows:
            a = r.find("a", class_="title")
            if not a or "/trophy/" not in a.get("href", ""):
                continue

            name = a.text.strip()
            href = a.get("href", "")
            parts = href.strip("/").split("/")
            m = re.match(r"^(\d+)-", parts[-1])
            psn_trophy_id = int(m.group(1)) if m else None

            # Detect trophy type (platinum, gold, silver, bronze)
            type_img = r.find("img", title=lambda t: bool(t and t.lower() in ("platinum", "gold", "silver", "bronze")))
            if not type_img:
                type_img = r.find("img", src=lambda s: bool(s and any(k in s.lower() for k in ("platinum", "gold", "silver", "bronze"))))

            if type_img and type_img.get("title") and type_img["title"].lower() in ("platinum", "gold", "silver", "bronze"):
                trophy_type = type_img["title"].lower()
            elif type_img and type_img.get("src"):
                for k in ("platinum", "gold", "silver", "bronze"):
                    if k in type_img["src"].lower():
                        trophy_type = k
                        break
                else:
                    trophy_type = "bronze"
            else:
                trophy_type = "bronze"

            # Extract description from text siblings of title anchor
            td = a.parent
            desc_parts = []
            for child in td.children:
                if child != a and getattr(child, "name", None) != "a":
                    txt = child.get_text(strip=True) if hasattr(child, "get_text") else str(child).strip()
                    if txt:
                        desc_parts.append(txt)
            description = " ".join(desc_parts).strip() or None

            trophies.append({
                "name": name,
                "psn_trophy_id": psn_trophy_id,
                "type": trophy_type,
                "description": description,
                "dlc": dlc,
            })

    return {
        "title": title,
        "trophies": trophies,
    }


def parse_guide_html(html_content: str) -> Dict[str, Any]:
    # Parse PSNProfiles guide overview and missable markers
    soup = BeautifulSoup(html_content, "html.parser")
    difficulty: Optional[Decimal] = None
    hours: Optional[int] = None
    playthroughs: Optional[int] = None

    # Parse overview tags
    for tag in soup.find_all(class_=["tag", "overview-info"]):
        top = tag.find(class_="typo-top")
        bottom = tag.find(class_="typo-bottom")
        if top and bottom:
            b_text = bottom.get_text(strip=True).lower()
            t_text = top.get_text(strip=True)
            if "difficulty" in b_text and difficulty is None:
                m = re.search(r"(\d+(?:\.\d+)?)", t_text)
                if m:
                    difficulty = Decimal(m.group(1))
            elif "hour" in b_text and hours is None:
                m = re.search(r"(\d+)", t_text.replace(",", ""))
                if m:
                    hours = int(m.group(1))
            elif "playthrough" in b_text and playthroughs is None:
                m = re.search(r"(\d+)", t_text)
                if m:
                    playthroughs = int(m.group(1))

    # Fallback via regex on entire page if missing
    full_text = soup.get_text()
    if difficulty is None:
        m = re.search(r"(\d+(?:\.\d+)?)(?:/\d+)?\s*(?:out of 10)?\s*Difficulty", full_text, re.IGNORECASE)
        if m:
            difficulty = Decimal(m.group(1))
    if hours is None:
        m = re.search(r"(\d+)\s*(?:-\s*\d+)?\s*Hours?", full_text, re.IGNORECASE)
        if m:
            hours = int(m.group(1))
    if playthroughs is None:
        m = re.search(r"(\d+)\s*Playthroughs?", full_text, re.IGNORECASE)
        if m:
            playthroughs = int(m.group(1))

    # Parse missable trophy names from roadmap tags and individual trophy sections
    missable_trophies: Set[str] = set()

    for tr in soup.find_all("tr"):
        tag_span = tr.find(class_="tag")
        if tag_span and "missable" in tag_span.text.lower():
            for a in tr.find_all("a"):
                name = a.text.strip()
                if name:
                    missable_trophies.add(name)

    for section in soup.find_all(class_="section-holder"):
        if section.get("id") == "SectionContainer1":
            continue
        tags = [t.text.strip().lower() for t in section.find_all(class_="tag")]
        if "missable" in tags:
            title_a = section.find("a", class_="title")
            if title_a and title_a.text.strip():
                missable_trophies.add(title_a.text.strip())

    return {
        "difficulty": difficulty,
        "hours": hours,
        "playthroughs": playthroughs,
        "missable_trophies": missable_trophies,
    }


async def import_catalog(
    game_id: str,
    trophies_html_path: str,
    guide_html_path: Optional[str] = None,
) -> Dict[str, Any]:
    # Ingest catalog and execute idempotent upsert into games and trophies tables
    with open(trophies_html_path, "r", encoding="utf-8") as f:
        trophies_html = f.read()

    default_title = game_id.replace("-", " ").title()
    trophies_data = parse_trophies_html(trophies_html, default_title=default_title)

    guide_data = None
    if guide_html_path:
        with open(guide_html_path, "r", encoding="utf-8") as f:
            guide_html = f.read()
        guide_data = parse_guide_html(guide_html)

    async with get_db_session() as session:
        # Upsert game record
        stmt_game = select(GameModel).where(GameModel.id == game_id)
        res_game = await session.execute(stmt_game)
        game = res_game.scalar_one_or_none()

        title = trophies_data.get("title") or default_title
        diff = guide_data["difficulty"] if guide_data else None
        hrs = guide_data["hours"] if guide_data else None
        pt = guide_data["playthroughs"] if guide_data else None

        if game:
            game.title = title
            if diff is not None:
                game.difficulty = diff
            if hrs is not None:
                game.hours = hrs
            if pt is not None:
                game.playthroughs = pt
            game.metadata_source = "psnprofiles"
        else:
            game = GameModel(
                id=game_id,
                title=title,
                difficulty=diff,
                hours=hrs,
                playthroughs=pt,
                metadata_source="psnprofiles",
            )
            session.add(game)

        await session.flush()

        # Upsert trophies
        stmt_trophies = select(TrophyModel).where(TrophyModel.game_id == game_id)
        res_trophies = await session.execute(stmt_trophies)
        existing_by_name = {t.name: t for t in res_trophies.scalars().all()}

        missables = guide_data["missable_trophies"] if guide_data else set()
        unlocated_count = 0

        for item in trophies_data["trophies"]:
            name = item["name"]
            psn_id = item.get("psn_trophy_id")
            trophy_type = item["type"]
            desc = item.get("description")
            dlc = item.get("dlc")
            is_missable = name in missables

            if name in existing_by_name:
                t = existing_by_name[name]
                t.psn_trophy_id = psn_id
                t.type = trophy_type
                t.description = desc
                t.dlc = dlc
                if is_missable:
                    t.missable = True
                    sources = list(t.missable_sources or [])
                    if "psnprofiles" not in sources:
                        sources.append("psnprofiles")
                    t.missable_sources = sources
                if not t.location:
                    unlocated_count += 1
            else:
                trophy_id = f"{game_id}-{slugify(name)}"
                sources = ["psnprofiles"] if is_missable else []
                t = TrophyModel(
                    id=trophy_id,
                    game_id=game_id,
                    psn_trophy_id=psn_id,
                    name=name,
                    type=trophy_type,
                    description=desc,
                    dlc=dlc,
                    location=None,
                    missable=is_missable,
                    missable_sources=sources,
                )
                session.add(t)
                unlocated_count += 1

        logger.info(f"{unlocated_count} trophies were left without location.")
        await session.commit()

        return {
            "game_id": game_id,
            "imported_trophies": len(trophies_data["trophies"]),
            "unlocated_trophies": unlocated_count,
        }


async def main():
    if len(sys.argv) < 3:
        print("Usage: python -m src.catalog.import GAME_ID TROPHIES_HTML [GUIDE_HTML]")
        sys.exit(1)

    game_id = sys.argv[1]
    trophies_html = sys.argv[2]
    guide_html = sys.argv[3] if len(sys.argv) > 3 else None

    res = await import_catalog(game_id, trophies_html, guide_html)
    print(f"Catalog import complete: {res['imported_trophies']} trophies imported for {game_id}.")
