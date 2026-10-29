import re
import hashlib
from typing import List, Optional
from src.schemas.chunk import DocumentChunk, IngestGuideRequest

# Ensure DocumentChunk accepts dynamic entity linking fields
DocumentChunk.model_config["extra"] = "allow"
DocumentChunk.model_rebuild(force=True)

MISSABLE_KEYWORDS = [
    "perdível",
    "perdivel",
    "missable",
    "ponto de não retorno",
    "point of no return",
    "atenção",
    "aviso crítico",
    "não avance",
    "antes de terminar",
]


class TrophyGuideChunker:
    """
    Semantic chunker optimized for PlayStation Trophy Guides.
    Splits by Markdown headings (#, ##, ###) to preserve trophy context boundaries,
    and falls back to character/token windowing with overlap for long narrative sections.
    """

    def __init__(self, max_chunk_size: int = 1200, chunk_overlap: int = 200):
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_guide(self, request: IngestGuideRequest) -> List[DocumentChunk]:
        raw_text = request.content.strip()
        if not raw_text:
            return []

        # Split text into sections using Markdown headers (H1, H2, H3)
        # Regex captures headings like `# Title`, `## Chapter 1`, `### Trophy Name`
        sections = re.split(r'\n(?=#{1,3}\s+)', raw_text)

        chunks: List[DocumentChunk] = []
        chunk_idx = 0

        for section in sections:
            section = section.strip()
            if not section:
                continue

            # Extract title from the first header line if available
            lines = section.splitlines()
            first_line = lines[0].strip()
            if first_line.startswith("#"):
                title = re.sub(r'^#{1,3}\s*', '', first_line).strip()
                content = "\n".join(lines[1:]).strip() if len(lines) > 1 else first_line
            else:
                title = f"{request.game} — Overview"
                content = section

            if not content:
                content = title

            # If section is small enough, keep it atomic (best for semantic trophy context)
            if len(content) <= self.max_chunk_size:
                chunks.append(self._create_chunk(
                    game=request.game,
                    title=title,
                    content=content,
                    source_url=request.source_url,
                    index=chunk_idx
                ))
                chunk_idx += 1
            else:
                # Section exceeds max size -> apply sliding window with overlap
                sub_chunks = self._split_with_overlap(content)
                for sub_i, sub_text in enumerate(sub_chunks):
                    sub_title = f"{title} (Part {sub_i + 1})"
                    chunks.append(self._create_chunk(
                        game=request.game,
                        title=sub_title,
                        content=sub_text,
                        source_url=request.source_url,
                        index=chunk_idx
                    ))
                    chunk_idx += 1

        return chunks

    def _split_with_overlap(self, text: str) -> List[str]:
        """
        Splits long continuous text blocks using a character window with overlap.
        Prefers breaking at paragraph boundaries or periods to preserve semantic coherence.
        """
        chunks: List[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.max_chunk_size, text_len)

            if end < text_len:
                # Try to break at a newline or period near the end (only in the forward region)
                min_break = start + self.chunk_overlap
                split_at = text.rfind("\n\n", min_break, end)
                if split_at == -1:
                    split_at = text.rfind(". ", min_break, end)
                if split_at != -1 and split_at > min_break:
                    end = split_at + 1

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)

            if end >= text_len:
                break

            # Advance by step size minus overlap, ensuring strict forward progress
            next_start = end - self.chunk_overlap
            start = max(next_start, start + 1)

        return chunks

    def _create_chunk(
        self,
        game: str,
        title: str,
        content: str,
        source_url: str,
        index: int
    ) -> DocumentChunk:
        # Check for missable markers in title and content
        searchable_text = f"{title} {content}".lower()
        is_missable = any(kw in searchable_text for kw in MISSABLE_KEYWORDS)

        # Deterministic chunk ID based on game, title, and index
        id_raw = f"{game}:{title}:{index}:{content[:50]}"
        chunk_id = hashlib.sha256(id_raw.encode("utf-8")).hexdigest()[:16]

        return DocumentChunk(
            chunk_id=chunk_id,
            game=game,
            title=title,
            content=content,
            is_missable=is_missable,
            metadata={
                "source_url": source_url,
                "chunk_index": index,
                "char_length": len(content),
            }
        )


chunker = TrophyGuideChunker()
MarkdownSemanticChunker = TrophyGuideChunker


def build_context_prefix(
    game: str,
    title: str,
    content: str = "",
    source_url: str = "",
    dlc: Optional[str] = None,
) -> str:
    """
    Builds context prefix: '<game title> › <DLC ou Base Game> › <section title>'
    for embedding and full-text tsvector indexing without changing user-facing content.
    If canonical dlc is specified, uses it (or 'Base Game' if None or empty).
    """
    if dlc is not None:
        scope = dlc if (dlc and dlc.strip()) else "Base Game"
    else:
        txt = f"{title} {content} {source_url}".lower()
        if (
            "hearts of stone" in txt
            or any(
                k.lower() in title.lower()
                for k in [
                    "when it's many against one",
                    "when it’s many against one",
                    "moo-rderer",
                    "return to sender",
                    "rad steez, bro!",
                    "wild rose dethorned",
                    "i wore ofieri before it was cool",
                    "killed it",
                ]
            )
        ):
            scope = "Hearts of Stone"
        elif "blood and wine" in txt:
            scope = "Blood and Wine"
        elif "dlc" in txt:
            scope = "DLC"
        else:
            scope = "Base Game"
    return f"{game} › {scope} › {title}"
