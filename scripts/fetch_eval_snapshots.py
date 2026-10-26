#!/usr/bin/env python3
"""
scripts/fetch_eval_snapshots.py

Baixa as fontes HTML listadas no golden set (golden_witcher3.json)
para services/ingest/tests/golden/snapshots/<nome>.html.
Se alguma URL falhar ou retornar bloqueio (ex.: Cloudflare 403), emite aviso
com instruções para salvar manualmente pelo navegador.
"""

import json
import re
import sys
from pathlib import Path
import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_JSON = REPO_ROOT / "services" / "ingest" / "tests" / "golden" / "golden_witcher3.json"
SNAPSHOTS_DIR = REPO_ROOT / "services" / "ingest" / "tests" / "golden" / "snapshots"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def extract_url(raw_text: str) -> str:
    m = re.search(r"https?://[^\s()]+", raw_text)
    if m:
        return m.group(0)
    return raw_text.strip()


def main():
    if not GOLDEN_JSON.exists():
        print(f"[ERRO] Golden set não encontrado em: {GOLDEN_JSON}", file=sys.stderr)
        sys.exit(1)

    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(GOLDEN_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    sources = data.get("sources", {})
    if not sources:
        print("[AVISO] Nenhuma fonte encontrada em 'sources'.")
        return

    print(f"=== Baixando snapshots para {SNAPSHOTS_DIR} ===")

    for name, raw_source in sources.items():
        url = extract_url(raw_source)
        dest_file = SNAPSHOTS_DIR / f"{name}.html"

        print(f"\n-> [{name}] {url}")
        try:
            resp = httpx.get(url, headers=HEADERS, follow_redirects=True, timeout=20.0)
            if resp.status_code == 200:
                dest_file.write_text(resp.text, encoding="utf-8")
                print(f"   [OK] Salvo com sucesso em {dest_file.name} ({len(resp.text)} bytes)")
            else:
                print(
                    f"   [AVISO] Falha ao baixar (HTTP {resp.status_code}).\n"
                    f"   Bloqueio detectado (ex.: Cloudflare).\n"
                    f"   Por favor, abra a URL no navegador e salve o HTML manualmente em:\n"
                    f"   {dest_file}"
                )
        except Exception as e:
            print(
                f"   [AVISO] Erro de rede: {e}\n"
                f"   Por favor, salve o HTML manualmente em:\n"
                f"   {dest_file}"
            )


if __name__ == "__main__":
    main()
