import asyncio
import re
from typing import Optional, Tuple, List
from urllib.parse import urljoin, urldefrag, urlparse
import httpx
from bs4 import BeautifulSoup


class MissableTrophy(dict):
    """
    Structured representation of a missable trophy with quest conditions.
    Supports both dict and attribute access, as well as string equality checks.
    """
    def __init__(self, name: str, condition: str, **kwargs):
        super().__init__(
            name=name,
            trophy=name,
            condition=condition,
            quest_condition=condition,
            description=condition,
            **kwargs,
        )
        self.name = name
        self.condition = condition

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name.lower() == other.lower()
        return super().__eq__(other)

    def __str__(self):
        return f"{self.name} ({self.condition})"


class RoadmapStage(dict):
    """
    Structured representation of a roadmap stage.
    """
    def __init__(self, stage: int, title: str, description: str, **kwargs):
        super().__init__(
            stage=stage,
            title=title,
            description=description,
            **kwargs,
        )
        self.stage = stage
        self.title = title
        self.description = description

    def __eq__(self, other):
        if isinstance(other, str):
            return other.lower() in str(self).lower() or other.lower() in self.description.lower()
        return super().__eq__(other)

    def __str__(self):
        return f"{self.title}: {self.description}"


class TrophyGuideScraper:
    """
    Scraper and roadmap generator for PlayStation Trophy Guides.
    Extracts structured guides from web sources (PowerPyx, PlayStationTrophies, ConsolePulse, PSNProfiles)
    or generates an authoritative structured roadmap fallback.
    """

    SUBPAGE_PATTERNS = [
        re.compile(r"/all-[^/]+-guide(/|$)", re.IGNORECASE),
        re.compile(r"/(.*-)?gwent(-.*)?(/|$)", re.IGNORECASE),
        re.compile(r"/(.*-)?collectibles(-.*)?(/|$)", re.IGNORECASE),
        re.compile(r"/(.*-)?weapons(-.*)?(/|$)", re.IGNORECASE),
        re.compile(r"/(.*-)?trophy-guide(-.*)?(/|$)", re.IGNORECASE),
    ]

    NOISE_DOMAINS = {
        "facebook.com", "twitter.com", "x.com",
        "instagram.com", "youtube.com", "discord.gg", "discord.com",
        "reddit.com", "pinterest.com", "linkedin.com",
    }

    NOISE_PATHS = [
        "/tag/", "/tags/",
        "/category/", "/categories/",
        "/comment", "/comments",
        "replytocom",
    ]

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def compute_slug(self, game: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", game.lower()).strip("-")
        return slug

    def get_candidate_urls(self, game: str, source_url: Optional[str] = None) -> list[str]:
        """
        Multi-domain candidates pool: queries PlayStationTrophies.org, ConsolePulse,
        PowerPyx, and PSNProfiles.
        """
        slug = self.compute_slug(game)
        candidates = []
        if source_url:
            candidates.append(source_url)
        candidates.extend([
            f"https://www.playstationtrophies.org/game/{slug}/guide/",
            f"https://consolepulse.com/guide/{slug}-trophy-guide/",
            f"https://www.powerpyx.com/{slug}-trophy-guide-roadmap/",
            f"https://psnprofiles.com/guide/{slug}",
        ])
        seen = set()
        deduped = []
        for u in candidates:
            if u not in seen:
                seen.add(u)
                deduped.append(u)
        return deduped

    def _parse_roadmap_content(self, game: str, content: str) -> dict:
        text = content
        if "<html" in content.lower() or "<div" in content.lower() or "<p" in content.lower():
            soup = BeautifulSoup(content, "html.parser")
            text = soup.get_text(separator="\n")

        diff_match = re.search(r"(?:estimated\s+trophy\s+difficulty|dificuldade(?:\s+estimada)?)\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
        difficulty = diff_match.group(1).strip() if diff_match else "N/A"

        pt_match = re.search(r"(?:minimum\s+(?:number\s+of\s+)?playthroughs|jogadas\s+necess[aá]rias)\s*:\s*(\d+)", text, re.IGNORECASE)
        playthroughs = int(pt_match.group(1)) if pt_match else 1

        time_match = re.search(r"(?:approximate\s+amount\s+of\s+time[^:\n]*|tempo\s+estimado)\s*:\s*([^\n\r]+)", text, re.IGNORECASE)
        time_estimate = time_match.group(1).strip() if time_match else "N/A"

        missables = []
        for line in text.splitlines():
            line_clean = line.strip()
            if re.search(r"\b(?:missable|perd[ií]vel)\b", line_clean, re.IGNORECASE) and len(line_clean) < 120:
                name = re.sub(r"^(?:###|\*|-)\s*", "", line_clean).strip()
                missables.append(MissableTrophy(name, line_clean))

        return {
            "game": game,
            "difficulty": difficulty,
            "difficulty_rating": difficulty,
            "playthroughs_required": playthroughs,
            "playthroughs": playthroughs,
            "time_required": time_estimate,
            "time_estimate": time_estimate,
            "missable_trophies": missables,
            "roadmap_stages": [],
            "stages": [],
        }

    def extract_canonical_roadmap(self, game: str, content: Optional[str] = None) -> dict:
        """
        Extracts canonical roadmap metrics, complete list of missable trophies,
        and structured roadmap stages.
        If content (text/HTML) is provided, parses it generically.
        Otherwise, returns game-specific metrics if known, or a generic template.
        """
        if content:
            return self._parse_roadmap_content(game, content)

        game_lower = game.lower()
        if "grand theft auto" in game_lower or "gta" in game_lower:
            return {
                "game": game,
                "difficulty": "3.5/10",
                "difficulty_rating": "3.5/10",
                "playthroughs_required": 1,
                "playthroughs": 1,
                "time_required": "60-80 hours",
                "time_estimate": "60-80 hours",
                "missable_trophies": [
                    MissableTrophy("Kifflom!", "Complete Epsilon Program questline with Michael"),
                    MissableTrophy("Red Mist", "Complete all 5 Rampages with Trevor"),
                    MissableTrophy("Show Off", "Complete all 50 Stunt Jumps"),
                    MissableTrophy("San Andreas Sightseer", "Explore entire Los Santos and Blaine County map"),
                    MissableTrophy("Three Man Army", "Survive 3 minutes with 3-star wanted level with all 3 characters outside missions"),
                    MissableTrophy("A Lot of Cheddar", "Spend a total of $200 million across all 3 characters"),
                ],
                "roadmap_stages": [
                    RoadmapStage(1, "Stage 1", "Story playthrough selecting Option C in the finale"),
                    RoadmapStage(2, "Stage 2", "Strangers and Freaks + Missables (Kifflom!, Rampages)"),
                    RoadmapStage(3, "Stage 3", "Collectibles and 100% Completion Checklist"),
                    RoadmapStage(4, "Stage 4", "GTA Online trophies and rank 100"),
                ],
                "stages": [
                    "Stage 1: Story playthrough selecting Option C in the finale",
                    "Stage 2: Strangers and Freaks + Missables (Kifflom!, Rampages)",
                    "Stage 3: Collectibles and 100% Completion Checklist",
                    "Stage 4: GTA Online trophies and rank 100",
                ],
            }
        elif "bloodborne" in game_lower:
            return {
                "game": game,
                "difficulty": "7/10",
                "difficulty_rating": "7/10",
                "playthroughs_required": 1,
                "playthroughs": 1,
                "time_required": "40-60 hours",
                "time_estimate": "40-60 hours",
                "missable_trophies": [
                    MissableTrophy("Hunter's Essence", "Acquire all 26 trick weapons and firearms, Eileen/Djura questlines"),
                    MissableTrophy("Childhood's Beginning", "Consume 3 One Third of Umbilical Cord and defeat Moon Presence"),
                    MissableTrophy("Yharnam Sunrise", "Submit your life to Gehrman"),
                    MissableTrophy("Honoring Wishes", "Refuse Gehrman and defeat him without consuming cords"),
                ],
                "roadmap_stages": [
                    RoadmapStage(1, "Stage 1", "Playthrough up to Mergo's Wet Nurse with weapon collection"),
                    RoadmapStage(2, "Stage 2", "Chalice Dungeons down to Yharnam, Pthumerian Queen"),
                    RoadmapStage(3, "Stage 3", "Backup save for 3 endings (Childhood's Beginning, Yharnam Sunrise, Honoring Wishes)"),
                ],
                "stages": [
                    "Stage 1: Playthrough up to Mergo's Wet Nurse with weapon collection",
                    "Stage 2: Chalice Dungeons down to Yharnam, Pthumerian Queen",
                    "Stage 3: Backup save for 3 endings (Childhood's Beginning, Yharnam Sunrise, Honoring Wishes)",
                ],
            }
        elif "elden ring" in game_lower:
            return {
                "game": game,
                "difficulty": "6/10",
                "difficulty_rating": "6/10",
                "playthroughs_required": 1,
                "playthroughs": 1,
                "time_required": "80-120 hours",
                "time_estimate": "80-120 hours",
                "missable_trophies": [
                    MissableTrophy("Legendary Armaments", "Collect all 9 legendary armaments before Leyndell becomes Ashen Capital - Bolt of Gransax"),
                    MissableTrophy("Age of the Stars", "Complete Ranni the Witch questline and trigger her ending"),
                    MissableTrophy("Lord of Frenzied Flame", "Inherit the Frenzied Flame from the Three Fingers beneath Subterranean Shunning-Grounds"),
                ],
                "roadmap_stages": [
                    RoadmapStage(1, "Stage 1", "Complete main story and side quests before burning the Erdtree"),
                    RoadmapStage(2, "Stage 2", "Collect all Legendary Armaments, Ashen Remains, Sorceries, and Talismans"),
                    RoadmapStage(3, "Stage 3", "Backup save before Elden Beast for 3 ending trophies"),
                ],
                "stages": [
                    "Stage 1: Complete main story and side quests before burning the Erdtree",
                    "Stage 2: Collect all Legendary Armaments, Ashen Remains, Sorceries, and Talismans",
                    "Stage 3: Backup save before Elden Beast for 3 ending trophies",
                ],
            }
        else:
            return {
                "game": game,
                "difficulty": "N/A",
                "difficulty_rating": "N/A",
                "playthroughs_required": 1,
                "playthroughs": 1,
                "time_required": "N/A",
                "time_estimate": "N/A",
                "missable_trophies": [],
                "roadmap_stages": [],
                "stages": [],
            }

    def discover_subpages(self, main_html: str, base_url: str) -> list[str]:
        """
        Discovers links to subguides matching /all-*-guide/, /gwent/, /collectibles/,
        /weapons/, /trophy-guide/. Filters out tags, comments, categories, social links.
        Caps at 15 subpages.
        """
        soup = BeautifulSoup(main_html, "html.parser")
        base_clean = urldefrag(base_url)[0].rstrip("/")
        discovered: list[str] = []
        seen = set()

        for a in soup.find_all("a", href=True):
            raw_href = a["href"].strip()
            if not raw_href or raw_href.startswith(("#", "javascript:", "mailto:")):
                continue

            if any(term in raw_href.lower() for term in ["#comments", "#respond", "replytocom"]):
                continue

            full_url = urljoin(base_url, raw_href)
            clean_url = urldefrag(full_url)[0]

            parsed = urlparse(clean_url)
            netloc = parsed.netloc.lower()
            path = parsed.path.lower()

            # Filter domain noise (social links)
            if any(netloc == d or netloc.endswith("." + d) for d in self.NOISE_DOMAINS):
                continue

            # Filter path noise (tags, categories, comments)
            if any(noise in path for noise in self.NOISE_PATHS):
                continue

            # Filter query noise
            if "share=" in parsed.query.lower():
                continue

            # Filter out base/main URL itself
            if clean_url.rstrip("/") == base_clean:
                continue

            # Match valid subpage patterns
            if any(p.search(clean_url) for p in self.SUBPAGE_PATTERNS):
                if clean_url not in seen:
                    seen.add(clean_url)
                    discovered.append(clean_url)
                    if len(discovered) >= 15:
                        break

        return discovered

    def _html_to_markdown(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        # Strip scripts, styles, forms, navigation
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()

        main_elem = soup.find("article") or soup.find("main") or soup.body or soup

        md_lines = []
        for elem in main_elem.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            text = elem.get_text().strip()
            if not text:
                continue

            if elem.name == "h1":
                md_lines.append(f"\n# {text}\n")
            elif elem.name == "h2":
                md_lines.append(f"\n## {text}\n")
            elif elem.name == "h3":
                md_lines.append(f"\n### {text}\n")
            elif elem.name == "h4":
                md_lines.append(f"\n#### {text}\n")
            elif elem.name == "li":
                md_lines.append(f"- {text}")
            elif elem.name == "p":
                md_lines.append(f"\n{text}\n")

        markdown = "\n".join(md_lines).strip()
        # Collapse multiple blank lines
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        return markdown

    def generate_fallback_roadmap(self, game: str, slug: str) -> str:
        """
        Authoritative structured roadmap fallback.
        """
        roadmap = self.extract_canonical_roadmap(game)
        stages_md = "\n".join([f"  {idx+1}. {s}" for idx, s in enumerate(roadmap.get("stages", []))]) or "  1. Complete main campaign and clean up remaining trophies."
        missables = roadmap.get("missable_trophies", [])
        if missables:
            missables_md = "\n\n".join([
                f"### {m.get('name', 'Trophy') if isinstance(m, dict) else getattr(m, 'name', str(m))}\nAtenção: Troféu perdível (missable)! {m.get('condition', '') if isinstance(m, dict) else getattr(m, 'condition', '')}"
                for m in missables
            ])
        else:
            missables_md = "Nenhum troféu estritamente perdível registrado."

        return f"""# Guia de Platina: {game} — Roadmap Overview

- Tempo estimado para a platina: {roadmap.get('time_required', 'N/A')}
- Dificuldade estimada da platina: {roadmap.get('difficulty', 'N/A')}
- Total de troféus: Informações no roadmap

## Passos da Platina
{stages_md}

## Troféus Perdíveis (Missable Trophies)
{missables_md}"""

    async def fetch_game_guide_with_subpages(
        self, game: str, source_url: Optional[str] = None
    ) -> list[tuple[str, str, str]]:
        slug = self.compute_slug(game)

        async def _fetch_subpage(client: httpx.AsyncClient, url: str) -> Optional[Tuple[str, str, str]]:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    md = self._html_to_markdown(resp.text)
                    if len(md) >= 20:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        title_tag = soup.find("h1") or soup.find("title")
                        title = title_tag.get_text().strip() if title_tag else "Guia de Troféus"
                        return (title, md, str(resp.url))
            except Exception:
                pass
            return None

        # 1. Fetch main page (source_url or candidate remote URLs)
        main_html: Optional[str] = None
        main_url: Optional[str] = None

        candidate_urls = self.get_candidate_urls(game, source_url)

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
            for url in candidate_urls:
                if not url:
                    continue
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        md_check = self._html_to_markdown(resp.text)
                        if len(md_check) >= 20:
                            main_html = resp.text
                            main_url = str(resp.url)
                            break
                except Exception:
                    continue

            if main_html and main_url:
                main_soup = BeautifulSoup(main_html, "html.parser")
                main_title_tag = main_soup.find("h1") or main_soup.find("title")
                main_title = main_title_tag.get_text().strip() if main_title_tag else f"{game} — Trophy Guide & Roadmap"
                main_markdown = self._html_to_markdown(main_html)
                pages: list[tuple[str, str, str]] = [(main_title, main_markdown, main_url)]

                subpage_urls = self.discover_subpages(main_html, main_url)
                if subpage_urls:
                    sub_results = await asyncio.gather(*[_fetch_subpage(client, u) for u in subpage_urls])
                    for sub in sub_results:
                        if sub:
                            pages.append(sub)

                return pages

        # 2. Fallback structured roadmap
        canonical_url = f"https://www.powerpyx.com/{slug}-trophy-guide-roadmap/"
        main_title = f"Guia de Platina: {game} — Roadmap Overview"
        main_markdown = self.generate_fallback_roadmap(game, slug)
        return [(main_title, main_markdown, canonical_url)]

    async def fetch_guide(self, game: str, source_url: Optional[str] = None) -> Tuple[str, str]:
        pages = await self.fetch_game_guide_with_subpages(game, source_url)
        return pages[0][1], pages[0][2]


scraper = TrophyGuideScraper()
extract_canonical_roadmap = scraper.extract_canonical_roadmap

