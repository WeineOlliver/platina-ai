import pytest
from src.schemas.search import SearchResultItem
from src.services.reranker import RerankerService, reranker_service


def _make_candidate(
    cid: str,
    title: str,
    content: str,
    similarity_score: float,
    is_missable: bool = False,
    game: str = "Elden Ring",
) -> SearchResultItem:
    return SearchResultItem(
        id=cid,
        game=game,
        title=title,
        content=content,
        is_missable=is_missable,
        source_url=f"https://example.com/{cid}",
        similarity_score=similarity_score,
        metadata={},
    )


def test_reranker_empty_candidates():
    service = RerankerService()
    results = service.rerank(query="Lança de Gransax", candidates=[], top_k=3)
    assert results == []


def test_reranker_top_k_greater_than_candidates():
    candidates = [
        _make_candidate("1", "Guia Geral", "Dicas do jogo.", 0.70),
        _make_candidate("2", "Troféus", "Lista de troféus.", 0.75),
    ]
    results = reranker_service.rerank(query="troféu", candidates=candidates, top_k=10)
    assert len(results) == 2
    assert results[0].id == "2"


def test_reranker_special_characters_query():
    candidates = [
        _make_candidate("1", "Armas Lendárias", "A Lança de Gransax é uma arma lendária.", 0.75),
        _make_candidate("2", "Escudos", "Lista de escudos pesados.", 0.70),
    ]
    query = "!!! ??? @@##$$%% ^^&&** ()__++ Lança de Gransax?!?!"
    results = reranker_service.rerank(query=query, candidates=candidates, top_k=2)
    assert len(results) == 2
    assert results[0].id == "1"


def test_reranker_elevates_title_and_exact_entity_match_over_generic_semantic():
    """
    Candidate A has higher initial semantic similarity (0.88) from broad topical overlap,
    while Candidate B has lower initial similarity (0.72) but has the exact target entity
    in its title and content. Reranker must elevate Candidate B to #1.
    """
    cand_generic = _make_candidate(
        cid="cand_generic",
        title="Dicas Gerais de Exploração em Leyndell",
        content="Leyndell é a capital real repleta de itens dourados, muralhas e inimigos difíceis.",
        similarity_score=0.88,
    )
    cand_exact_entity = _make_candidate(
        cid="cand_exact_entity",
        title="Troféu Perdível: Lança de Gransax",
        content="Arma lendária na lança gigante cravada em Leyndell antes de Maliketh.",
        similarity_score=0.72,
        is_missable=True,
    )

    results = reranker_service.rerank(
        query="Onde achar a Lança de Gransax?",
        candidates=[cand_generic, cand_exact_entity],
        top_k=2,
    )

    assert len(results) == 2
    assert results[0].id == "cand_exact_entity"
    assert results[0].similarity_score > results[1].similarity_score


def test_reranker_boosts_boss_and_trophy_entities():
    cand_unrelated_boss = _make_candidate(
        cid="boss_generic",
        title="Estratégia para Chefes Menores",
        content="Dicas de combate contra avatares da Térvore e sentinelas da árvore.",
        similarity_score=0.82,
    )
    cand_target_boss = _make_candidate(
        cid="boss_target",
        title="Chefe: Maliketh, a Lâmina Negra",
        content="Como derrotar Maliketh em Farum Azula. Cuidado com o efeito de morte destinada.",
        similarity_score=0.74,
    )

    results = reranker_service.rerank(
        query="como derrotar o boss Maliketh",
        candidates=[cand_unrelated_boss, cand_target_boss],
        top_k=2,
    )

    assert results[0].id == "boss_target"
