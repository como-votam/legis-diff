#!/usr/bin/env python3
"""Baixa documentos públicos reais para validação manual do Legis Diff."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw"

SOURCES: list[tuple[str, str]] = [
    (
        "lc95.html",
        "https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp95.htm",
    ),
    (
        "lei14133.html",
        "https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm",
    ),
    (
        "lei8666.html",
        "https://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm",
    ),
    (
        "cf88.html",
        "https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm",
    ),
    (
        "cf88_compilado.html",
        "https://www.planalto.gov.br/ccivil_03/constituicao/constituicaocompilado.htm",
    ),
    (
        "decreto9191.html",
        "https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2017/decreto/d9191.htm",
    ),
    (
        "senado_lc95.html",
        "https://legis.senado.leg.br/norma/572850/publicacao/15771437",
    ),
]

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _download(url: str, dest: Path) -> None:
    curl = shutil.which("curl")
    if curl:
        subprocess.run(
            [
                curl,
                "-fsSL",
                "--retry",
                "3",
                "--retry-delay",
                "2",
                "-A",
                UA,
                "-o",
                str(dest),
                url,
            ],
            check=True,
        )
        return
    import httpx

    with httpx.Client(
        headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"},
        follow_redirects=True,
        timeout=60.0,
        http2=False,
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        dest.write_bytes(response.content)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for name, url in SOURCES:
        dest = OUT / name
        print(f"GET {url}")
        try:
            _download(url, dest)
            print(f"  → {dest} ({dest.stat().st_size} bytes)")
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERRO: {exc}", file=sys.stderr)
    print(f"{ok}/{len(SOURCES)} arquivos baixados em {OUT}")
    return 0 if ok == len(SOURCES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
