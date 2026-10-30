"""
run.py - CLI runner for Platina AI ingestion pipeline v2.
Usage:
    python -m src.pipeline.run --game the-witcher-3-wild-hunt --stage parse|link|check|load|all
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

from src.pipeline.sources import get_sources_for_game, SourceEntry
from src.pipeline.parsers import get_parser_for_kind
from src.pipeline.link import run_link
from src.pipeline.checks import run_checks
from src.pipeline.chunk import run_chunk
from src.pipeline.load import run_load


def get_game_data_dirs(game_id: str) -> dict[str, Path]:
    """Resolve and ensure data directories for the game."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    data_dir = base_dir / "data" / game_id
    raw_dir = data_dir / "raw"
    parsed_dir = data_dir / "parsed"
    linked_dir = data_dir / "linked"

    raw_dir.mkdir(parents=True, exist_ok=True)
    parsed_dir.mkdir(parents=True, exist_ok=True)
    linked_dir.mkdir(parents=True, exist_ok=True)

    return {
        "base": base_dir,
        "data": data_dir,
        "raw": raw_dir,
        "parsed": parsed_dir,
        "linked": linked_dir,
    }


def execute_parse_stage(game_id: str, dirs: dict[str, Path], sources: List[SourceEntry]) -> None:
    """Execute parser stage for all registered sources of the game."""
    print(f"\n==> [1/5] Executando etapa 'parse' para o jogo: {game_id}")
    for source in sources:
        source_path = source.resolve_path(base_dir=dirs["base"])
        print(f"  -> Parseando fonte '{source.id}' (kind: {source.kind}) a partir de {source.file}...")
        if not source_path.exists():
            raise FileNotFoundError(f"Arquivo HTML bruto não encontrado: {source_path}")

        parser_fn = get_parser_for_kind(source.kind)
        # Calling parser stub (will raise NotImplementedError)
        parsed_artifact = parser_fn(source_path)

        out_file = dirs["parsed"] / f"{source.id}.json"
        out_file.write_text(parsed_artifact.model_dump_json(indent=2), encoding="utf-8")
        print(f"     [OK] Gravado artefato inspecionável em {out_file.name}")


def execute_link_stage(game_id: str, dirs: dict[str, Path]) -> None:
    """Execute entity linking stage merging parsed sources."""
    print(f"\n==> [2/5] Executando etapa 'link' para o jogo: {game_id}")
    linked_game = run_link(game_id, dirs["data"])
    out_file = dirs["linked"] / "game.json"
    out_file.write_text(linked_game.model_dump_json(indent=2), encoding="utf-8")
    print(f"     [OK] Gravado artefato inspecionável em {out_file.name}")


def execute_check_stage(game_id: str, dirs: dict[str, Path]) -> None:
    """Execute consistency and invariant checks."""
    print(f"\n==> [3/5] Executando etapa 'check' para o jogo: {game_id}")
    run_checks(game_id, dirs["data"])
    print("     [OK] Todas as verificações de invariantes passaram.")


def execute_chunk_stage(game_id: str, dirs: dict[str, Path]) -> None:
    """Execute semantic chunking stage."""
    print(f"\n==> [4/5] Executando etapa 'chunk' para o jogo: {game_id}")
    run_chunk(game_id, dirs["data"])
    print("     [OK] Chunking semântico concluído.")


def execute_load_stage(game_id: str, dirs: dict[str, Path]) -> None:
    """Execute database loading stage."""
    print(f"\n==> [5/5] Executando etapa 'load' para o jogo: {game_id}")
    run_load(game_id, dirs["data"])
    print("     [OK] Carga no banco de dados concluída com sucesso.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Platina AI Ingestion Pipeline CLI v2")
    parser.add_argument(
        "--game",
        type=str,
        default="the-witcher-3-wild-hunt",
        help="Canonical game identifier (e.g. the-witcher-3-wild-hunt)",
    )
    parser.add_argument(
        "--stage",
        type=str,
        choices=["parse", "link", "check", "chunk", "load", "all"],
        default="all",
        help="Pipeline stage to execute (parse, link, check, chunk, load, all)",
    )

    args = parser.parse_args()
    game_id = args.game.strip()
    stage = args.stage.lower().strip()

    print(f"============================================================")
    print(f" Platina AI Pipeline v2: {game_id} (Etapa: {stage})")
    print(f"============================================================")

    dirs = get_game_data_dirs(game_id)
    try:
        sources = get_sources_for_game(game_id)
    except Exception as e:
        print(f"\n[ERRO] Falha ao carregar registro de fontes para '{game_id}': {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if stage in ("parse", "all"):
            execute_parse_stage(game_id, dirs, sources)

        if stage in ("link", "all"):
            execute_link_stage(game_id, dirs)

        if stage in ("check", "all"):
            execute_check_stage(game_id, dirs)

        if stage in ("chunk", "all"):
            execute_chunk_stage(game_id, dirs)

        if stage in ("load", "all"):
            execute_load_stage(game_id, dirs)

        print("\n[SUCESSO] Pipeline concluído com sucesso!")
    except NotImplementedError as e:
        print(f"\n[ERRO] Etapa não implementada: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERRO] Falha durante a execução do pipeline: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
