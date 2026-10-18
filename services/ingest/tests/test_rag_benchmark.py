import pytest
from httpx import AsyncClient, ASGITransport
from src.main import create_app

# Golden dataset guides covering Bloodborne, Elden Ring, and Grand Theft Auto V
GOLD_GUIDE_BLOODBORNE = """# Guia Completo de Troféus - Bloodborne

## Troféu Perdível: Hunter's Essence (Essência do Caçador)
Para o troféu Hunter's Essence você deve coletar todas as armas de caçador. Atenção crítica: este troféu é perdível (missable). A arma Blade of Mercy é obtida através da questline de Eileen the Crow em Central Yharnam antes de derrotar Rom. Se Rom for derrotado prematuramente, Eileen desaparecerá e a quest falhará.

## Troféu Perdível: Yharnam Sunrise (Amanhecer em Yharnam)
Para conquistar Yharnam Sunrise no final do jogo, você deve aceitar a proposta de Gehrman no Sonho do Caçador (Hunter's Dream) para se submeter à morte e despertar sem lutar contra ele. Se recusar, você entrará em combate e perderá este final no playthrough atual.

## Troféu: Blood Gem Master (Mestre da Gema de Sangue)
Obtenha uma gema de sangue extremamente preciosa de grau 15 ou superior. Essas gemas raras de poder transcendental são encontradas nos Cálices de Masmorra avançados (Chalice Dungeons profundidade 5).

## Troféu: Weapon Master (Mestre das Armas)
Aprimore qualquer arma de caçador ao nível máximo (+10). Requer Blood Stone Shards, Twin Shards, Chunks e uma Pedra de Sangue (Blood Rock) encontrada no Pesadelo de Mensis (Nightmare of Mensis).
"""

GOLD_GUIDE_ELDEN_RING = """# Guia Completo de Troféus - Elden Ring

## Troféu Perdível: Lança de Gransax (Bolt of Gransax)
Missable extremo! Esta arma lendária fica fincada na lança gigante cravada em Leyndell, Capital Real. Ela DEVE ser coletada antes de derrotar Maliketh em Farum Azula. Após Farum Azula, Leyndell vira a Capital das Cinzas e a lanca fica inacessível para sempre no seu playthrough atual.

## Troféu Perdível: Espada de Ranni (Dark Moon Greatsword)
Atenção crítica: Este troféu é perdível (missable). A questline de Ranni deve ser avançada antes de queimar a Térvore (Erdtree) com a Chama dos Gigantes em Forge of the Giants. Se você derrotar Maliketh antes de entregar o Anel do Juramento Escuro, Ranni desaparecerá e você não conseguirá o final Age of Stars nem a arma lendária Dark Moon Greatsword.

## Troféu: Godrick, o Enxertado
Derrote Godrick, o Enxertado no Castelo Tempesvéu (Stormveil Castle). Troféu obrigatório da história principal que não pode ser perdido.

## Troféu: Malenia, Lâmina de Miquella (Shardbearer Malenia)
Derrote Malenia, a Lâmina de Miquella na base da Árvore Sacra de Miquella (Haligtree). Chefe semideus opcional lendário para o troféu Shardbearer.
"""

GOLD_GUIDE_GTA_V = """# Guia Completo de Troféus - Grand Theft Auto V

## Troféu: Masterminds (Criminoso Mestre / Criminal Mastermind)
Conquiste o troféu Masterminds completando todos os 3 Atos do Golpe do Juízo Final (The Doomsday Heist) em ordem, com a mesma equipe e sem morrer ou perder nenhuma vida em GTA Online. Exige extrema coordenação tática para não zerar o progresso dos golpes.

## Troféu Perdível: Kifflom! e o Programa Epsilon
Troféu Kifflom! obtido completando todas as missões do Programa Epsilon com Michael. Requer doar fundos no site da Epsilon, comprar e vestir a túnica por 10 dias seguidos e caminhar 8 quilômetros no deserto de Grand Senora. Atenção crítica para não falhar a entrega final do dinheiro.
"""

GOLD_GUIDE_WITCHER_3 = """# Guia Completo de Troféus - The Witcher 3: Wild Hunt

## Troféu Perdível: Full Crew (Equipe Completa)
Recrute todos os aliados possíveis para Kaer Morhen antes de viajar para a Ilha das Brumas (Isle of Mists). Atenção crítica: este troféu é missable (perdível). Conclua as linhas de missões de Keira Metz, Vernon Roche, Zoltan Chivay, Ermion e os governantes de Skellige antes de avançar além do ponto de não retorno.

## Troféu Perdível: Card Collector (Colecionador de Cartas)
Atenção: Este troféu é missable (perdível)! Adquira todas as 199 cartas de Gwent únicas no jogo base espalhadas por Pomar Branco (White Orchard), Velen, Novigrad e Skellige. Certas cartas de torneios e personagens expiram permanentemente se você avançar sem conquistá-las.

## Troféu Perdível: Assassin of Kings (Assassino de Reis)
Atenção: Troféu perdível (missable)! Participe do complô contra o Rei Radovid na quest Reason of State. Conclua as missões secundárias An Eye for an Eye, A Deadly Plot, Redania's Most Wanted e Reason of State. Não agrida Dijkstra nos banhos públicos.

## Troféu Perdível: Friends With Benefits (Amigos com Benefícios)
Atenção: Troféu perdível (missable)! Conclua toda a linha de missões de Keira Metz sem matar a feiticeira. Convença Keira a ir para Kaer Morhen.

## Troféu Perdível: Gwent Master (Mestre do Gwent)
Atenção: Troféu perdível (missable)! Vença o torneio High Stakes no bordel Passiflora em Novigrad com 1000 coroas e baralho forte.

## Troféu Perdível: Kingmaker (Criador de Reis)
Atenção: Troféu perdível (missable)! Complete a linha de missões de sucessão do trono de Skellige apoiando Cerys ou Hjalmar an Craite.

## Troféu Perdível: Even Odds (Pau a Pau)
Atenção: Troféu perdível (missable)! Conclua 2 contratos de bruxo matando os monstros sem usar sinais, poções, mutagênicos, óleos ou bombas.

## Troféu Perdível: Fast and Furious (Velozes e Furiosos)
Atenção: Troféu perdível (missable)! Vença todas as corridas de cavalo em Velen, Novigrad e Skellige.

## Troféu Perdível: The Doppler Effect (O Efeito Doppler)
Atenção: Troféu perdível (missable)! Conclua o contrato de bruxo Um Ladrão Elusivo (An Elusive Thief) em Novigrad resolvendo o problema do doppler.

## Troféu Perdível: Woodland Spirit (Espírito da Floresta)
Atenção: Troféu perdível (missable)! Conclua o contrato do Leshen em Skellige ficando do lado de Sven para matar o monstro.

## Troféu Perdível: White Orchard innkeeper (Estalajadeira do Pomar Branco)
Atenção: Carta altamente perdível (missable)! Compre todas as cartas de Gwent da White Orchard innkeeper Elsa logo no início na taverna do Pomar Branco antes de partir para Vizima.

## Troféu Perdível: Dandelion in Vegelbud Masquerade (Dandelion no Baile dos Vegelbud)
Atenção: Carta estritamente perdível (missable)! Vença as 3 partidas no torneio de Gwent durante o baile de máscaras com Triss na propriedade Vegelbud (Vegelbud Masquerade) para ganhar a carta Dandelion.
"""

# 10 Ground-Truth Benchmark Cases (Bloodborne, Elden Ring, and GTA V)
BENCHMARK_10_SCENARIOS = [
    # Bloodborne (4 scenarios)
    {
        "id": "BB-01",
        "game": "Bloodborne",
        "description": "Busca por arma missable Blade of Mercy da questline de Eileen the Crow",
        "query": "Blade of Mercy Eileen the Crow Hunter's Essence armas de caçador missable",
        "expected_trophy": "Hunter's Essence",
        "expected_missable": True,
        "critical_term": "eileen",
    },
    {
        "id": "BB-02",
        "game": "Bloodborne",
        "description": "Busca pelo final Yharnam Sunrise com proposta pacífica de Gehrman",
        "query": "Yharnam Sunrise proposta de Gehrman Hunter's Dream despertar sem lutar",
        "expected_trophy": "Yharnam Sunrise",
        "expected_missable": True,
        "critical_term": "gehrman",
    },
    {
        "id": "BB-03",
        "game": "Bloodborne",
        "description": "Busca por gema de sangue de grau máximo em Chalice Dungeons",
        "query": "Blood Gem Master gema de sangue preciosa Chalice Dungeons profundidade",
        "expected_trophy": "Blood Gem Master",
        "expected_missable": False,
        "critical_term": "cálices",
    },
    {
        "id": "BB-04",
        "game": "Bloodborne",
        "description": "Busca pelo troféu de arma +10 com Blood Rock no Pesadelo de Mensis",
        "query": "Weapon Master aprimorar arma nível máximo Blood Rock Mensis",
        "expected_trophy": "Weapon Master",
        "expected_missable": False,
        "critical_term": "mensis",
    },
    # Elden Ring (4 scenarios)
    {
        "id": "ER-01",
        "game": "Elden Ring",
        "description": "Busca pelo troféu altamente perdível Bolt of Gransax em Leyndell antes de Maliketh",
        "query": "Lança de Gransax Bolt of Gransax Leyndell missable Maliketh cinzas",
        "expected_trophy": "Lança de Gransax",
        "expected_missable": True,
        "critical_term": "maliketh",
    },
    {
        "id": "ER-02",
        "game": "Elden Ring",
        "description": "Busca pela questline de Ranni, espada lendária e final Age of Stars",
        "query": "Ranni Dark Moon Greatsword Age of Stars Térvore missable",
        "expected_trophy": "Espada de Ranni",
        "expected_missable": True,
        "critical_term": "ranni",
    },
    {
        "id": "ER-03",
        "game": "Elden Ring",
        "description": "Busca por chefe mandatório da história Godrick no Castelo Tempesvéu",
        "query": "Godrick Enxertado Castelo Tempesvéu Stormveil chefe história",
        "expected_trophy": "Godrick",
        "expected_missable": False,
        "critical_term": "tempesvéu",
    },
    {
        "id": "ER-04",
        "game": "Elden Ring",
        "description": "Busca pelo troféu Shardbearer Malenia na Árvore Sacra de Haligtree",
        "query": "Malenia Lâmina de Miquella Haligtree Árvore Sacra Shardbearer",
        "expected_trophy": "Malenia",
        "expected_missable": False,
        "critical_term": "haligtree",
    },
    # GTA V (2 scenarios)
    {
        "id": "GTA-01",
        "game": "Grand Theft Auto V",
        "description": "Busca pelo troféu Masterminds do Golpe do Juízo Final sem perder vidas",
        "query": "Masterminds Criminal Mastermind Golpes Doomsday Heist sem morrer",
        "expected_trophy": "Masterminds",
        "expected_missable": False,
        "critical_term": "doomsday",
    },
    {
        "id": "GTA-02",
        "game": "Grand Theft Auto V",
        "description": "Busca pelo troféu perdível Kifflom e missões do Programa Epsilon no deserto",
        "query": "Kifflom Programa Epsilon Michael deserto túnica dinheiro",
        "expected_trophy": "Kifflom",
        "expected_missable": True,
        "critical_term": "epsilon",
    },
]

# Witcher 3 Ground-Truth Multi-Source Canonical Benchmark Cases
WITCHER_3_BENCHMARK_SCENARIOS = [
    {
        "id": "TW3-01",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Recrutamento de aliados para Kaer Morhen antes de Isle of Mists",
        "query": "Full Crew recrute todos os aliados Kaer Morhen Isle of Mists missable",
        "expected_trophy": "Full Crew",
        "expected_missable": True,
        "critical_term": "kaer morhen",
    },
    {
        "id": "TW3-02",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Coleta de todas as cartas de Gwent em todas as regiões",
        "query": "Card Collector todas as cartas de Gwent missable White Orchard Velen Novigrad Skellige",
        "expected_trophy": "Card Collector",
        "expected_missable": True,
        "critical_term": "gwent",
    },
    {
        "id": "TW3-03",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Complô contra o Rei Radovid na quest Reason of State",
        "query": "Assassin of Kings complô contra Radovid Reason of State missable",
        "expected_trophy": "Assassin of Kings",
        "expected_missable": True,
        "critical_term": "radovid",
    },
    {
        "id": "TW3-04",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Linha de missões de Keira Metz sem matá-la",
        "query": "Friends With Benefits linha de missões Keira Metz sem matar missable",
        "expected_trophy": "Friends With Benefits",
        "expected_missable": True,
        "critical_term": "keira",
    },
    {
        "id": "TW3-05",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Torneio High Stakes no Passiflora",
        "query": "Gwent Master torneio High Stakes Passiflora missable",
        "expected_trophy": "Gwent Master",
        "expected_missable": True,
        "critical_term": "passiflora",
    },
    {
        "id": "TW3-06",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Linha de sucessão do trono de Skellige apoiando Cerys ou Hjalmar",
        "query": "Kingmaker sucessão Skellige Cerys Hjalmar missable",
        "expected_trophy": "Kingmaker",
        "expected_missable": True,
        "critical_term": "skellige",
    },
    {
        "id": "TW3-07",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Matar 2 contratos de bruxo sem sinais, poções, mutagênicos, óleos ou bombas",
        "query": "Even Odds matar 2 monstros contratos de bruxo sem sinais pocoes bombas missable",
        "expected_trophy": "Even Odds",
        "expected_missable": True,
        "critical_term": "contratos",
    },
    {
        "id": "TW3-08",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Vencer todas as corridas de cavalo em Velen, Novigrad e Skellige",
        "query": "Fast and Furious vença todas as corridas de cavalo Velen Novigrad Skellige missable",
        "expected_trophy": "Fast and Furious",
        "expected_missable": True,
        "critical_term": "corridas",
    },
    {
        "id": "TW3-09",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Contrato de bruxo Um Ladrão Elusivo em Novigrad",
        "query": "The Doppler Effect contrato Um Ladrão Elusivo Novigrad missable",
        "expected_trophy": "The Doppler Effect",
        "expected_missable": True,
        "critical_term": "novigrad",
    },
    {
        "id": "TW3-10",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Contrato Leshen em Skellige ficando do lado de Sven",
        "query": "Woodland Spirit contrato Leshen Sven Skellige missable",
        "expected_trophy": "Woodland Spirit",
        "expected_missable": True,
        "critical_term": "leshen",
    },
    {
        "id": "TW3-GWENT-01",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Cartas perdíveis da estalajadeira do Pomar Branco",
        "query": "White Orchard innkeeper Elsa cartas de Gwent Pomar Branco taverna missable",
        "expected_trophy": "White Orchard innkeeper",
        "expected_missable": True,
        "critical_term": "pomar branco",
    },
    {
        "id": "TW3-GWENT-02",
        "game": "The Witcher 3: Wild Hunt",
        "description": "Carta Dandelion no torneio do baile dos Vegelbud com Triss",
        "query": "Dandelion in Vegelbud Masquerade baile mascaras Triss torneio Gwent",
        "expected_trophy": "Dandelion in Vegelbud Masquerade",
        "expected_missable": True,
        "critical_term": "vegelbud",
    },
]

# Unrelated and out-of-scope queries that must be filtered out
OUT_OF_SCOPE_QUERIES = [
    "Receita culinária de bolo de cenoura fofinho com cobertura de brigadeiro",
    "Como trocar o óleo e filtro de um trator agrícola John Deere",
    "Bitcoin blockchain proof of work hash mining satoshi nakamoto",
    "Passo a passo declaração de imposto de renda pessoa física",
]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def async_client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
async def seed_benchmark_gold_guides(async_client):
    """Seed the database with the gold standard guides across all 3 games."""
    await async_client.post(
        "/api/v1/ingest/reindex",
        json={
            "game": "Bloodborne",
            "source_url": "https://powerpyx.com/bloodborne-trophy-guide",
            "content": GOLD_GUIDE_BLOODBORNE,
        },
    )
    await async_client.post(
        "/api/v1/ingest/reindex",
        json={
            "game": "Elden Ring",
            "source_url": "https://powerpyx.com/elden-ring-trophy-guide",
            "content": GOLD_GUIDE_ELDEN_RING,
        },
    )
    await async_client.post(
        "/api/v1/ingest/reindex",
        json={
            "game": "Grand Theft Auto V",
            "source_url": "https://powerpyx.com/gta-5-trophy-guide",
            "content": GOLD_GUIDE_GTA_V,
        },
    )
    await async_client.post(
        "/api/v1/ingest/reindex",
        json={
            "game": "The Witcher 3: Wild Hunt",
            "source_url": "https://powerpyx.com/witcher-3-trophy-guide",
            "content": GOLD_GUIDE_WITCHER_3,
        },
    )


@pytest.mark.anyio
async def test_hybrid_retrieval_100_percent_recall_at_3_on_gold_dataset(async_client):
    """
    Validates that hybrid retrieval (BM25 + pgvector + Reranker) achieves 100% Recall@3
    across all 10 real benchmark scenarios (Bloodborne, Elden Ring, and GTA V).
    """
    successful_recalls = 0
    total_scenarios = len(BENCHMARK_10_SCENARIOS)

    for scenario in BENCHMARK_10_SCENARIOS:
        response = await async_client.post(
            "/api/v1/ingest/search",
            json={
                "query": scenario["query"],
                "game": scenario["game"],
                "limit": 3,
                "min_similarity": 0.65,
            },
        )
        assert response.status_code == 200, f"Search failed for {scenario['id']}"
        data = response.json()

        results = data.get("results", [])
        assert len(results) > 0, f"Expected results for scenario {scenario['id']}, got 0"

        # Check Recall@3: Is expected trophy present in top 3 results?
        top_3_titles = [r["title"].lower() for r in results[:3]]
        found_in_top_3 = any(scenario["expected_trophy"].lower() in title for title in top_3_titles)

        assert found_in_top_3, (
            f"Recall@3 failed for {scenario['id']} ({scenario['game']}): "
            f"Expected '{scenario['expected_trophy']}' in top 3 titles {top_3_titles}"
        )

        # Quality check: Top hit contains critical operational keyword
        top_hit = results[0]
        assert scenario["critical_term"].lower() in top_hit["content"].lower(), (
            f"Top hit for {scenario['id']} missing critical keyword '{scenario['critical_term']}'"
        )

        # Cutoff check: Retrieved chunks must satisfy similarity threshold (>= 0.65)
        assert top_hit["similarity_score"] >= 0.65, (
            f"Similarity score {top_hit['similarity_score']} below cutoff 0.65 for {scenario['id']}"
        )

        # Missable flag verification
        if scenario["expected_missable"]:
            assert top_hit["is_missable"] is True, f"Expected missable flag for {scenario['id']}"

        successful_recalls += 1

    recall_at_3 = successful_recalls / total_scenarios
    assert recall_at_3 == 1.0, f"Expected 100% Recall@3, got {recall_at_3 * 100:.1f}%"


@pytest.mark.anyio
async def test_unrelated_queries_drop_to_zero_results_due_to_similarity_cutoff(async_client):
    """
    Asserts that queries for unrelated or out-of-scope topics drop to 0 results
    due to the similarity threshold cutoff (>= 0.65).
    """
    for query in OUT_OF_SCOPE_QUERIES:
        # 1. Search without game filter
        response = await async_client.post(
            "/api/v1/ingest/search",
            json={
                "query": query,
                "limit": 3,
                "min_similarity": 0.65,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_results"] == 0, (
            f"Unrelated query '{query}' returned {data['total_results']} results (expected 0)"
        )
        assert len(data["results"]) == 0

        # 2. Search with game filter
        response_with_game = await async_client.post(
            "/api/v1/ingest/search",
            json={
                "query": query,
                "game": "Elden Ring",
                "limit": 3,
                "min_similarity": 0.65,
            },
        )
        assert response_with_game.status_code == 200
        data_with_game = response_with_game.json()
        assert data_with_game["total_results"] == 0
        assert len(data_with_game["results"]) == 0


@pytest.mark.anyio
async def test_witcher_3_canonical_roadmap_and_gwent_100_percent_recall(async_client):
    """
    Validates that hybrid retrieval (BM25 + pgvector + Reranker) achieves 100% Recall@3
    across all Witcher 3 canonical missables and Gwent subpage scenarios.
    """
    successful_recalls = 0
    total_scenarios = len(WITCHER_3_BENCHMARK_SCENARIOS)

    for scenario in WITCHER_3_BENCHMARK_SCENARIOS:
        response = await async_client.post(
            "/api/v1/ingest/search",
            json={
                "query": scenario["query"],
                "game": scenario["game"],
                "limit": 3,
                "min_similarity": 0.65,
            },
        )
        assert response.status_code == 200, f"Search failed for {scenario['id']}"
        data = response.json()

        results = data.get("results", [])
        assert len(results) > 0, f"Expected results for scenario {scenario['id']}, got 0"

        # Check Recall@3: Is expected trophy present in top 3 results?
        top_3_titles = [r["title"].lower() for r in results[:3]]
        found_in_top_3 = any(scenario["expected_trophy"].lower() in title for title in top_3_titles)

        assert found_in_top_3, (
            f"Recall@3 failed for {scenario['id']} ({scenario['game']}): "
            f"Expected '{scenario['expected_trophy']}' in top 3 titles {top_3_titles}"
        )

        # Quality check: Top hit contains critical operational keyword
        top_hit = results[0]
        assert scenario["critical_term"].lower() in top_hit["content"].lower(), (
            f"Top hit for {scenario['id']} missing critical keyword '{scenario['critical_term']}'"
        )

        # Cutoff check: Retrieved chunks must satisfy similarity threshold (>= 0.65)
        assert top_hit["similarity_score"] >= 0.65, (
            f"Similarity score {top_hit['similarity_score']} below cutoff 0.65 for {scenario['id']}"
        )

        # Missable flag verification
        if scenario["expected_missable"]:
            assert top_hit["is_missable"] is True, f"Expected missable flag for {scenario['id']}"

        successful_recalls += 1

    recall_at_3 = successful_recalls / total_scenarios
    assert recall_at_3 == 1.0, f"Expected 100% Recall@3 for Witcher 3, got {recall_at_3 * 100:.1f}%"

