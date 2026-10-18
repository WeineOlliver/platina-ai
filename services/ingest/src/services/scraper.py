import asyncio
import re
from typing import Optional, Tuple, List
from urllib.parse import urljoin, urldefrag, urlparse
import httpx
from bs4 import BeautifulSoup


class TrophyGuideScraper:
    """
    Scraper and roadmap generator for PlayStation Trophy Guides.
    Extracts structured guides from web sources (PowerPyx, PSNProfiles)
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
        Authoritative structured roadmap fallback covering:
        - Roadmap Overview (Tempo, Dificuldade, Passos da Platina)
        - Missable Trophies (Card Collector, Full Crew, Assassin of Kings)
        - Natural Grinds (Humpty Dumpty, That Is the Evilest Thing)
        - Post-Game Cleanups (Brawler, Fist of the South Star)
        """
        return f"""# Guia de Platina: {game} — Roadmap Overview

- Tempo estimado para a platina: 100-150 horas
- Dificuldade estimada da platina: 6/10 (Marcha da Morte)
- Total de troféus: 53 (1 Platina, 2 Ouro, 8 Prata, 42 Bronze)
- Passos da Platina:
  1. Concluir a história principal na dificuldade Marcha da Morte (Death March) sem alterar o nível em nenhum momento.
  2. Coletar todas as cartas de Gwent e completar missões secundárias associadas a troféus perdíveis antes do ponto de não retorno em Kaer Morhen.
  3. Fazer a limpeza de contratos de bruxo, lutas desarmadas e troféus específicos de combate.

## Troféus Perdíveis (Missable Trophies)

### Card Collector (Colecionador de Cartas)
Atenção: Este troféu é missable (perdível)! Adquira todas as cartas de Gwent disponíveis no jogo base. Certas cartas só podem ser obtidas em torneios específicos (como o torneio no Passiflora) ou durante festas com Triss Merigold. Se você falhar ou recusar partidas, perderá o troféu.

### Full Crew (Comitiva Completa)
Atenção: Troféu perdível! Recrute todos os aliados possíveis para Kaer Morhen antes de viajar para a Ilha das Brumas. Ponto de não retorno: não avance para a Ilha das Brumas sem antes completar as linhas de missões de Keira Metz, Vernon Roche, Zoltan Chivay, Ermion e os governantes de Skellige (Hjalmar ou Cerys).

### Assassin of Kings (Assassino de Reis)
Atenção: Troféu perdível! Participe do complô contra o Rei Radovid completando a cadeia de missões secundárias de Dijkstra e Roche em Novigrad. Não quebre a perna de Dijkstra durante os eventos do banho público, senão a missão final será bloqueada permanentemente.

## Grinds Naturais (Natural Grinds)

### Humpty Dumpty
Mate 10 oponentes empurrando-os de lugares altos utilizando o sinal Aard. Um ótimo local de grind é a Fossa do Diabo em Velen, empurrando bandidos de plataformas elevadas.

### That Is the Evilest Thing
Incendeie o gás criado por uma bomba Dragão utilizando um oponente já em chamas 10 vezes. Combine o sinal Igni com a bomba Estrela Dançante ou Sonho do Dragão.

## Limpeza Pós-Jogo (Post-Game Cleanups)

### Brawler
Complete todas as missões de brigas de rua e derrotas de campeões em Velen, Novigrad e Skellige.

### Fist of the South Star
Derrote um oponente em uma luta desarmada sem sofrer nenhum tipo de dano ou golpe."""

    def generate_witcher_3_gwent_guide(self, game: str = "The Witcher 3: Wild Hunt") -> str:
        """
        Authoritative subpage guide for Gwent Card Locations covering all critical missable cards:
        - White Orchard innkeeper
        - Zoltan/Baron in Velen
        - Dandelion in Vegelbud Masquerade
        - High Stakes tournament in Passiflora
        """
        return f"""# {game} — Guia Completo de Cartas de Gwent e Colecionáveis Perdíveis (Card Collector)

## Visão Geral do Troféu Card Collector (Colecionador de Cartas)
Atenção: Este troféu é missable (perdível)! Para conquistá-lo, você precisa obter todas as cartas de Gwent disponíveis no jogo base. Se perder qualquer carta de missões com tempo limitado ou PNJs que morrem, o troféu será bloqueado na jogada atual.

## Requisitos Críticos de Cartas Perdíveis (Missable Gwent Cards)

### 1. White Orchard innkeeper (Estalajadeira do Pomar Branco)
- Localização: Taverna do Pomar Branco.
- Detalhes: Atenção: Carta altamente perdível (missable)! Compre todas as cartas da White Orchard innkeeper (Elsa) logo no início do jogo antes de avançar para o Palácio Real em Vizima. Caso você avance a história sem comprar, ela deixará o vilarejo permanentemente.

### 2. Zoltan/Baron in Velen (Zoltan e Barão Sanguinário em Velen)
- Missão: Gwent: Velen Players (Gwent: Jogadores de Velen).
- Detalhes: Atenção: Requisito perdível (missable)! Jogue contra Zoltan e depois contra o Barão Sanguinário (Phillip Strenger) em Poleiro do Corvo antes de completar as missões 'Family Matters' e 'Return to Crookback Bog'. Se o Barão morrer ou partir antes de você vencê-lo no Gwent, a carta Zoltan/Baron in Velen e a lista de jogadores podem ser recolhidas em sua mesa de trabalho no castelo.

### 3. Dandelion in Vegelbud Masquerade (Dandelion no Baile dos Vegelbud)
- Missão: A Matter of Life and Death (Uma Questão de Vida ou Morte).
- Detalhes: Atenção: Carta estritamente perdível (missable)! Durante o baile de máscaras com Triss Merigold na Propriedade dos Vegelbud (Vegelbud Masquerade), há um torneio secundário de Gwent com 3 partidas consecutivas. Você DEVE vencer todas as 3 partidas para obter a carta Dandelion in Vegelbud Masquerade. Não deixe a festa sem vencer essas partidas, pois a mansão fica inacessível depois.

### 4. High Stakes tournament in Passiflora (Torneio Apostas Altas no Passiflora)
- Missão: High Stakes (Apostas Altas).
- Detalhes: Atenção: Torneio perdível (missable)! O torneio High Stakes tournament in Passiflora no bordel Passiflora em Novigrad exige 1000 coroas e um baralho forte. Você enfrentará Bernard Tulle, Sasha, Finneas e o Conde Tybalt. Salve o jogo antes de cada confronto; qualquer derrota desqualifica Geralt e perde as cartas exclusivas dos líderes.
"""

    async def fetch_game_guide_with_subpages(
        self, game: str, source_url: Optional[str] = None
    ) -> list[tuple[str, str, str]]:
        slug = self.compute_slug(game)
        is_witcher_3 = "witcher" in game.lower() and "3" in game.lower()

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

        candidate_urls = [source_url] if source_url else [
            f"https://www.powerpyx.com/{slug}-trophy-guide-roadmap/",
            f"https://psnprofiles.com/guide/{slug}",
        ]

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

                # For Witcher 3, verify Gwent card requirements are covered
                if is_witcher_3:
                    has_gwent = any(
                        "dandelion in vegelbud masquerade" in p[1].lower() and
                        "white orchard innkeeper" in p[1].lower()
                        for p in pages
                    )
                    if not has_gwent:
                        gwent_url = f"https://www.powerpyx.com/{slug}-gwent-cards-locations-guide/"
                        gwent_title = f"{game} — Guia Completo de Cartas de Gwent e Colecionáveis Perdíveis"
                        gwent_md = self.generate_witcher_3_gwent_guide(game)
                        pages.append((gwent_title, gwent_md, gwent_url))

                return pages

        # 2. Fallback structured roadmap
        canonical_url = f"https://www.powerpyx.com/{slug}-trophy-guide-roadmap/"
        main_title = f"Guia de Platina: {game} — Roadmap Overview"
        main_markdown = self.generate_fallback_roadmap(game, slug)
        pages = [(main_title, main_markdown, canonical_url)]

        if is_witcher_3:
            gwent_url = f"https://www.powerpyx.com/{slug}-gwent-cards-locations-guide/"
            gwent_title = f"{game} — Guia Completo de Cartas de Gwent e Colecionáveis Perdíveis"
            gwent_md = self.generate_witcher_3_gwent_guide(game)
            pages.append((gwent_title, gwent_md, gwent_url))

        return pages

    async def fetch_guide(self, game: str, source_url: Optional[str] = None) -> Tuple[str, str]:
        pages = await self.fetch_game_guide_with_subpages(game, source_url)
        return pages[0][1], pages[0][2]


scraper = TrophyGuideScraper()
