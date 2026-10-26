import asyncio
import logging
import re
from typing import Optional, Tuple, List
from urllib.parse import quote_plus, urljoin, urldefrag, urlparse
import httpx
from bs4 import BeautifulSoup
from src.services.browser import fetch_rendered_html

logger = logging.getLogger(__name__)


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

    NOISE_TROPHY_NAMES = {
        "missable", "perdível", "perdivel", "troféus perdíveis", "trofeus perdiveis",
        "yes", "no", "none", "n/a", "na", "trophy", "trophies",
        "overview", "roadmap", "guide", "introduction", "stage 1", "stage 2",
        "stage 3", "stage 4", "trophy guide", "roadmap overview",
        "playstation", "xbox", "steam", "pc", "comments", "leave a reply",
        "all trophies", "platinum trophy",
        "basics", "side quests", "miscellaneous", "story-related",
        "things that could go wrong", "things that could go wrong / what is missable",
    }

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

    async def discover_guide_urls(self, game: str) -> list[str]:
        """
        Queries PowerPyx internal search and falls back cleanly to canonical
        patterns for PlayStationTrophies, PSNProfiles, PowerPyx, and ConsolePulse.
        """
        slug = self.compute_slug(game)
        canonical = [
            f"https://www.powerpyx.com/{slug}-trophy-guide-roadmap/",
            f"https://www.playstationtrophies.org/game/{slug}/guide/",
            f"https://psnprofiles.com/guide/{slug}",
            f"https://consolepulse.com/guide/{slug}-trophy-guide/",
        ]
        discovered: list[str] = []

        search_url = f"https://www.powerpyx.com/?s={quote_plus(game)}"
        search_html: Optional[str] = None
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
                resp = await client.get(search_url)
                if resp.status_code == 200:
                    search_html = resp.text
                elif resp.status_code == 403:
                    search_html = await fetch_rendered_html(search_url, timeout=self.timeout)
        except Exception as exc:
            logger.warning("Search request failed for %s: %s", game, exc)

        if search_html:
            try:
                soup = BeautifulSoup(search_html, "html.parser")
                articles = soup.find_all("article")
                candidate_links: list[tuple[str, str]] = []
                if articles:
                    for art in articles:
                        h = art.find(["h1", "h2", "h3"])
                        a = h.find("a", href=True) if h else art.find("a", href=True)
                        if a:
                            candidate_links.append((a["href"].strip(), a.get_text(strip=True)))
                else:
                    for a in soup.find_all("a", href=True):
                        candidate_links.append((a["href"].strip(), a.get_text(strip=True)))

                game_slug_tokens = set(re.sub(r"[^a-zA-Z0-9]+", " ", game.lower()).split())
                game_slug_tokens = {t for t in game_slug_tokens if t not in {"the", "a", "an", "and", "of", "in", "for"}}

                for raw_href, link_text in candidate_links:
                    if not raw_href.startswith("http"):
                        raw_href = urljoin("https://www.powerpyx.com", raw_href)
                    href_clean = urldefrag(raw_href)[0]
                    parsed = urlparse(href_clean)
                    path = parsed.path.rstrip("/")
                    lower_path = path.lower()
                    lower_url = clean_url = href_clean.lower()

                    if path in ("", "/guides", "/guide", "/category", "/tag", "/news", "/all-guides"):
                        continue
                    if any(noise in lower_path for noise in self.NOISE_PATHS):
                        continue
                    if "powerpyx.com" not in parsed.netloc.lower():
                        continue

                    is_guide_path = (
                        "-trophy-guide" in lower_path
                        or "-guide" in lower_path
                        or "/guides/" in lower_path
                        or "/guide/" in lower_path
                    )
                    if not is_guide_path:
                        continue

                    text_and_url = lower_url + " " + link_text.lower()
                    if game_slug_tokens and not any(t in text_and_url for t in game_slug_tokens):
                        continue

                    if href_clean not in discovered:
                        discovered.append(href_clean)
            except Exception as exc:
                logger.warning("Error parsing search results for %s: %s", game, exc)

        candidates = []
        seen = set()
        for u in discovered + canonical:
            if u not in seen:
                seen.add(u)
                candidates.append(u)
        return candidates

    def _normalize_trophy_name(self, name: str) -> str:
        name = re.sub(r"<[^>]+>", "", name)
        name = re.sub(r"^(?:#{1,6}|\*|-|\d+\.)\s*", "", name)
        name = re.sub(r"^(?:missable|perd[ií]vel|trof[eé]u\s+perd[ií]vel)\s*[:\-]\s*", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s*[\[\(]\s*(?:missable|perd[ií]vel)\s*[\]\)]", "", name, flags=re.IGNORECASE)
        name = re.sub(r"\s*-\s*(?:missable|perd[ií]vel)$", "", name, flags=re.IGNORECASE)
        name = name.strip(" \t\n\r\"'`:.-")
        return name

    def _is_valid_trophy_name(self, name: str) -> bool:
        if not name or len(name) < 2 or len(name) > 80:
            return False
        lower = name.lower()
        if lower in self.NOISE_TROPHY_NAMES:
            return False
        if re.match(r"^\d+$", lower):
            return False
        if any(term in lower for term in ["guide", "roadmap", "walkthrough", "trophy list", "troféus perdíveis", "trofeus perdiveis", "missable trophies", "passos da platina"]):
            return False
        if lower.startswith(("http://", "https://", "www.")):
            return False
        if re.match(r"^\d+\s*hours?$", lower) or re.match(r"^\d+/\d+$", lower):
            return False
        return True

    def parse_roadmap_dom(self, html: str, base_url: str = "") -> dict:
        """
        Uses BeautifulSoup to parse genuine community guide structures:
        extracts Difficulty, Playthroughs, Missable trophies, and Subpage links.
        """
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n")

        # 1. Difficulty
        difficulty = "N/A"
        for dt in soup.find_all(["dt", "th", "strong", "b"]):
            if "difficulty" in dt.get_text().lower() or "dificuldade" in dt.get_text().lower():
                dd = dt.find_next_sibling(["dd", "td", "span"])
                if dd and dd.get_text(strip=True):
                    m = re.search(r"(\d+(?:\.\d+)?\s*/\s*10|\d+(?:\.\d+)?)", dd.get_text(strip=True))
                    if m:
                        difficulty = m.group(1).replace(" ", "")
                        if "/" not in difficulty and float(difficulty) <= 10:
                            difficulty = f"{difficulty}/10"
                        break
        if difficulty == "N/A":
            m = re.search(
                r"(?:estimated\s+trophy\s+difficulty|trophy\s+difficulty|dificuldade(?:\s+estimada)?|difficulty)\s*[:\-]?\s*(\d+(?:\.\d+)?(?:\s*/\s*10)?)",
                text,
                re.IGNORECASE,
            )
            if m:
                val = m.group(1).replace(" ", "")
                if "/" not in val and float(val) <= 10:
                    difficulty = f"{val}/10"
                else:
                    difficulty = val

        # 2. Playthroughs
        playthroughs = 1
        for dt in soup.find_all(["dt", "th", "strong", "b"]):
            if "playthrough" in dt.get_text().lower() or "jogadas" in dt.get_text().lower():
                dd = dt.find_next_sibling(["dd", "td", "span"])
                if dd and dd.get_text(strip=True):
                    m = re.search(r"(\d+)", dd.get_text(strip=True))
                    if m:
                        playthroughs = int(m.group(1))
                        break
        if playthroughs == 1:
            m = re.search(
                r"(?:minimum\s+(?:number\s+of\s+)?playthroughs?|playthroughs?(?:\s+required)?|jogadas\s+necess[aá]rias)\s*[:\-]?\s*(\d+)",
                text,
                re.IGNORECASE,
            )
            if m:
                playthroughs = int(m.group(1))

        # 3. Time estimate
        time_estimate = "N/A"
        for dt in soup.find_all(["dt", "th", "strong", "b"]):
            if "time" in dt.get_text().lower() or "tempo" in dt.get_text().lower():
                dd = dt.find_next_sibling(["dd", "td", "span"])
                if dd and dd.get_text(strip=True):
                    time_estimate = dd.get_text(strip=True)
                    break
        if time_estimate == "N/A":
            m = re.search(
                r"(?:approximate\s+amount\s+of\s+time[^:\n<]*|time\s+to\s+platinum|tempo\s+estimado|estimated\s+time)\s*[:\-]?\s*([^\n\r<]+)",
                text,
                re.IGNORECASE,
            )
            if m:
                time_estimate = m.group(1).strip()

        # 4. Missable Trophies
        missables: list[str] = []
        seen = set()

        def add_candidate(raw: str):
            norm = self._normalize_trophy_name(raw)
            if self._is_valid_trophy_name(norm) and norm.lower() not in seen:
                seen.add(norm.lower())
                missables.append(norm)

        # Tag-based / class-based
        missable_elements = soup.find_all(
            lambda tag: (
                (tag.get("class") and any("missable" in c.lower() for c in tag.get("class")))
                or (tag.name in ["span", "strong", "b", "em", "div", "a"] and re.search(r"^\s*\[?\b(?:missable|perd[ií]vel)\b\]?\s*$", tag.get_text(), re.IGNORECASE))
            )
        )

        for el in missable_elements:
            container = el.find_parent(["tr", "li", "div", "article", "section"])
            found_in_container = False
            if container:
                title_el = container.select_one(".title, a.title, .trophy-title, .trophy_name, h2, h3, h4, h5")
                if title_el:
                    c_text = title_el.get_text(strip=True)
                    if c_text and not re.search(r"^\s*\[?\b(?:missable|perd[ií]vel)\b\]?\s*$", c_text, re.IGNORECASE):
                        add_candidate(c_text)
                        found_in_container = True
            if not found_in_container:
                prev_h = el.find_previous(["h1", "h2", "h3", "h4", "h5"])
                if prev_h:
                    add_candidate(prev_h.get_text(strip=True))

        # Overview paragraphs
        for p in soup.find_all(["p", "li", "dd"]):
            p_text = p.get_text()
            if re.search(r"\b(?:missable\s+trophies|number\s+of\s+missable\s+trophies|trof[eé]us\s+perd[ií]veis)\b", p_text, re.IGNORECASE):
                anchors = p.find_all("a")
                if anchors:
                    for a in anchors:
                        add_candidate(a.get_text(strip=True))
                else:
                    m = re.search(r"[:\-–]\s*(.*)$", p_text.strip())
                    if m:
                        rest = m.group(1)
                        rest = re.sub(r"^\d+\s*[-–:]?\s*", "", rest)
                        rest = rest.strip("()")
                        for item in re.split(r"[,;]", rest):
                            add_candidate(item)

        # Paragraphs or sections containing explicit missable trophy notices
        for p in soup.find_all(["p", "div", "li", "tr"]):
            p_text = p.get_text()
            if re.search(r"\b(?:is\s+(?:highly\s+)?missable|trof[eé]u\s+perd[ií]vel|missable\s+trophy)\b", p_text, re.IGNORECASE):
                lines = [l.strip() for l in p_text.splitlines() if l.strip()]
                if lines:
                    first_line = lines[0]
                    if not any(k in first_line.lower() for k in ["things that could", "playlist", "click here", "warning"]):
                        add_candidate(first_line)

        # Markdown headings / bullet points
        current_heading = None
        for line in text.splitlines():
            line_s = line.strip()
            if re.match(r"^#{1,6}\s+", line_s):
                current_heading = re.sub(r"^#{1,6}\s+", "", line_s).strip()
            elif re.search(r"\b(?:missable|perd[ií]vel)\b", line_s, re.IGNORECASE):
                if re.match(r"^(?:#{1,6}|\*|-)\s*", line_s):
                    add_candidate(line_s)
                elif current_heading:
                    add_candidate(current_heading)

        # 5. Subpage links
        subpage_urls = self.discover_subpages(html, base_url) if base_url else []
        if not subpage_urls:
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href or href.startswith(("#", "javascript:", "mailto:")):
                    continue
                if any(noise in href.lower() for noise in self.NOISE_PATHS):
                    continue
                if any(p.search(href) for p in self.SUBPAGE_PATTERNS) or any(t in href.lower() for t in ["collectibles", "cards", "weapons", "trophy-guide"]):
                    if href not in subpage_urls:
                        subpage_urls.append(href)

        return {
            "difficulty": difficulty,
            "difficulty_rating": difficulty,
            "playthroughs": playthroughs,
            "playthroughs_required": playthroughs,
            "time_estimate": time_estimate,
            "time_required": time_estimate,
            "missable_trophies": missables,
            "subpage_urls": subpage_urls,
            "subpages": subpage_urls,
        }

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
        Otherwise, returns a generic template.
        """
        if content:
            return self._parse_roadmap_content(game, content)

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
        for tag in soup.find_all(["aside", "footer", "header", "nav"]):
            tag.decompose()
        for tag in soup.find_all(class_=lambda c: c and any(x in " ".join(c).lower() for x in ["sidebar", "widget", "recent-post"])):
            tag.decompose()

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

            # Filter out base/main URL itself or generic index pages
            if clean_url.rstrip("/") == base_clean:
                continue

            if any(clean_url.rstrip("/").endswith(root) for root in ["/trophy-guide", "/trophy-guides", "/guides", "/guide", "/upcoming-guides", "/trophy-lists"]):
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
                cls = elem.get("class") or []
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                if any(c in ["style96", "style93", "trophy-entry"] for c in cls) and lines:
                    title_candidate = lines[0]
                    if self._is_valid_trophy_name(title_candidate) and len(title_candidate) < 70 and not title_candidate.lower().startswith(("the playlist", "click here", "things that could")):
                        md_lines.append(f"\n### {title_candidate}\n")
                        if len(lines) > 1:
                            md_lines.append("\n".join(lines[1:]) + "\n")
                        continue
                md_lines.append(f"\n{text}\n")

        markdown = "\n".join(md_lines).strip()
        # Collapse multiple blank lines
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        return markdown

    async def fetch_game_guide_with_subpages(
        self, game: str, source_url: Optional[str] = None
    ) -> list[tuple[str, str, str, str]]:
        slug = self.compute_slug(game)

        async def _fetch_html(client: httpx.AsyncClient, url: str) -> Optional[str]:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code == 403:
                    rendered = await fetch_rendered_html(url, timeout=self.timeout)
                    if rendered:
                        return rendered
            except Exception:
                pass
            return None

        async def _fetch_subpage(client: httpx.AsyncClient, url: str) -> Optional[Tuple[str, str, str, str]]:
            html = await _fetch_html(client, url)
            if html:
                md = self._html_to_markdown(html)
                if len(md) >= 20:
                    soup = BeautifulSoup(html, "html.parser")
                    title_tag = soup.find("h1") or soup.find("title")
                    title = title_tag.get_text().strip() if title_tag else "Guia de Troféus"
                    return (title, md, url, html)
            return None

        # 1. Fetch main page (source_url or candidate remote URLs from discover_guide_urls)
        main_html: Optional[str] = None
        main_url: Optional[str] = None

        candidate_urls = await self.discover_guide_urls(game)
        if source_url:
            candidate_urls = [source_url] + [u for u in candidate_urls if u != source_url]

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True, headers=self.headers) as client:
            for url in candidate_urls:
                if not url:
                    continue
                html = await _fetch_html(client, url)
                if html:
                    md_check = self._html_to_markdown(html)
                    if len(md_check) >= 20:
                        main_html = html
                        main_url = url
                        break

            if main_html and main_url:
                main_soup = BeautifulSoup(main_html, "html.parser")
                main_title_tag = main_soup.find("h1") or main_soup.find("title")
                main_title = main_title_tag.get_text().strip() if main_title_tag else f"{game} — Trophy Guide & Roadmap"
                main_markdown = self._html_to_markdown(main_html)
                pages: list[tuple[str, str, str, str]] = [(main_title, main_markdown, main_url, main_html)]

                subpage_urls = self.discover_subpages(main_html, main_url)
                if subpage_urls:
                    sub_results = await asyncio.gather(*[_fetch_subpage(client, u) for u in subpage_urls])
                    for sub in sub_results:
                        if sub:
                            pages.append(sub)

                return pages

        # 2. Return empty list if no guide pages could be fetched
        return []

    async def fetch_guide(self, game: str, source_url: Optional[str] = None) -> Tuple[str, str]:
        pages = await self.fetch_game_guide_with_subpages(game, source_url)
        if not pages:
            return "", ""
        return pages[0][1], pages[0][2]


scraper = TrophyGuideScraper()
extract_canonical_roadmap = scraper.extract_canonical_roadmap
discover_guide_urls = scraper.discover_guide_urls
parse_roadmap_dom = scraper.parse_roadmap_dom

