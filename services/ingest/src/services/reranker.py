import re
import unicodedata
from typing import List, Set
from src.schemas.search import SearchResultItem

STOPWORDS: Set[str] = {
    "a", "o", "as", "os", "de", "do", "da", "dos", "das", "em", "no", "na",
    "nos", "nas", "para", "por", "com", "um", "uma", "uns", "umas", "e", "ou",
    "que", "se", "como", "onde", "quando", "qual", "quais", "the", "an", "of",
    "in", "to", "for", "on", "with", "at", "by", "is", "are"
}

BOSS_MARKERS: Set[str] = {"boss", "chefe", "bosses", "chefes"}
TROPHY_MARKERS: Set[str] = {"trofeu", "trofeus", "trophy", "trophies", "platina", "conquista", "achievement"}
MISSABLE_MARKERS: Set[str] = {"perdivel", "perdiveis", "missable", "atencao", "perder"}


def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and removing accents/diacritics."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    unaccented = "".join(c for c in nfkd if not unicodedata.combining(c))
    return unaccented.lower()


def _match_term(term: str, words_set: Set[str], full_text: str) -> bool:
    """Match a term exactly, as a substring, or by common prefix stem (with minimum length guards)."""
    if term in words_set:
        return True
    if len(term) >= 3 and term in full_text:
        return True
    if len(term) >= 4:
        stem = term[:4]
        for w in words_set:
            if len(w) >= 4 and (w.startswith(stem) or term.startswith(w[:4])):
                return True
    return False


class RerankerService:
    """
    Lightweight zero-heavy-dependency cross-scoring reranker service.
    Combines normalized lexical term coverage, phrase proximity bonus,
    title match weighting, high-specificity entity boosts, and initial similarity.
    """

    def rerank(
        self,
        query: str,
        candidates: List[SearchResultItem],
        top_k: int = 3,
    ) -> List[SearchResultItem]:
        if not candidates or top_k <= 0:
            return []

        if not query or not query.strip():
            sorted_candidates = sorted(candidates, key=lambda x: x.similarity_score, reverse=True)
            return sorted_candidates[:top_k]

        query_norm = normalize_text(query)
        raw_tokens = [w for w in re.findall(r"\w+", query_norm) if len(w) > 0]
        query_terms = [t for t in raw_tokens if t not in STOPWORDS and len(t) > 1]
        if not query_terms:
            query_terms = [t for t in raw_tokens if len(t) > 1] or raw_tokens

        # Extract capitalized entities / proper nouns from raw query
        proper_nouns = [
            normalize_text(w)
            for w in re.findall(r"\b[A-ZÀ-Ú][a-zà-ú0-9_]+\b", query)
            if normalize_text(w) not in STOPWORDS and len(w) > 1
        ]

        has_boss_query = any(w in raw_tokens for w in BOSS_MARKERS)
        has_trophy_query = any(w in raw_tokens for w in TROPHY_MARKERS)
        has_missable_query = any(w in raw_tokens for w in MISSABLE_MARKERS)

        scored_candidates: List[tuple[float, SearchResultItem]] = []
        cross_scores: List[float] = []

        # First pass: calculate cross-scores for each candidate
        for item in candidates:
            title_norm = normalize_text(item.title)
            content_norm = normalize_text(item.content)
            title_words = set(re.findall(r"\w+", title_norm))
            content_words = set(re.findall(r"\w+", content_norm))

            # 1. Normalized Lexical Coverage (Title weighted heavily over content)
            if query_terms:
                title_matches = sum(1 for t in query_terms if _match_term(t, title_words, title_norm))
                content_matches = sum(1 for t in query_terms if _match_term(t, content_words, content_norm))
                title_cov = title_matches / len(query_terms)
                content_cov = content_matches / len(query_terms)
                lexical_score = (2.5 * title_cov + 1.0 * content_cov) / 3.5
            else:
                lexical_score = 0.0

            # 2. Phrase Proximity Bonus
            phrase_bonus = 0.0
            clean_phrase = " ".join(query_terms)
            if clean_phrase and len(query_terms) > 1:
                if clean_phrase in title_norm:
                    phrase_bonus = 1.0
                elif clean_phrase in content_norm:
                    phrase_bonus = 0.7
                else:
                    bigrams = [" ".join(query_terms[i:i + 2]) for i in range(len(query_terms) - 1)]
                    bg_title = sum(1 for bg in bigrams if bg in title_norm)
                    bg_content = sum(1 for bg in bigrams if bg in content_norm)
                    if bg_title > 0:
                        phrase_bonus = min(0.6, 0.3 * bg_title)
                    elif bg_content > 0:
                        phrase_bonus = min(0.4, 0.2 * bg_content)
            elif len(query_terms) == 1 and query_terms[0] in title_words:
                phrase_bonus = 0.6

            # 3. High-Specificity Entities Boost
            entity_bonus = 0.0
            if proper_nouns:
                pn_title = sum(1 for pn in proper_nouns if _match_term(pn, title_words, title_norm))
                pn_content = sum(1 for pn in proper_nouns if _match_term(pn, content_words, content_norm))
                pn_score = (2.0 * pn_title + 1.0 * pn_content) / (2.0 * len(proper_nouns))
                entity_bonus += 0.5 * min(1.0, pn_score)

            if has_boss_query:
                if any(m in title_words for m in BOSS_MARKERS) or any(m in content_words for m in BOSS_MARKERS):
                    entity_bonus += 0.25

            if has_trophy_query:
                if any(m in title_words for m in TROPHY_MARKERS) or any(m in content_words for m in TROPHY_MARKERS):
                    entity_bonus += 0.25

            if has_missable_query and item.is_missable:
                entity_bonus += 0.25

            if item.is_missable and any(m in title_words for m in MISSABLE_MARKERS):
                entity_bonus += 0.15

            entity_bonus = min(1.0, entity_bonus)

            cross_score = 0.45 * lexical_score + 0.30 * phrase_bonus + 0.25 * entity_bonus
            cross_scores.append(cross_score)
            scored_candidates.append((cross_score, item))

        # Check if any candidate had cross signal
        any_cross_signal = any(cs > 0.01 for cs in cross_scores)

        # Second pass: calculate final reranked score
        reranked_items: List[SearchResultItem] = []
        for cross_score, item in scored_candidates:
            if not any_cross_signal:
                final_score = item.similarity_score
            else:
                # Modulate similarity: items with strong cross signals get up to +20% boost,
                # items with zero cross signals get scaled down to 70% of base similarity
                final_score = item.similarity_score * (0.70 + 0.50 * cross_score)

            final_score = min(1.0, max(0.0, final_score))
            updated_item = item.model_copy(update={"similarity_score": round(final_score, 4)})
            reranked_items.append(updated_item)

        # Sort descending by final score (with original similarity as tiebreaker)
        reranked_items.sort(key=lambda x: x.similarity_score, reverse=True)
        return reranked_items[:top_k]


reranker_service = RerankerService()
