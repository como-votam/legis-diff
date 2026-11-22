#!/usr/bin/env python3
"""Validação manual end-to-end: exemplos + documentos baixados."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legisdiff.diff import diff_documents  # noqa: E402
from legisdiff.io import load_document  # noqa: E402
from legisdiff.patch import render_patch  # noqa: E402


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def show_stats(path: Path) -> None:
    doc = load_document(path)
    from collections import Counter

    counts = Counter(d.kind for d in doc.devices)
    print(f"\n{path.name}: {len(doc.devices)} dispositivos")
    if doc.epigrafe:
        print(f"  epígrafe: {doc.epigrafe[:100]}")
    for kind, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:12]:
        print(f"  {kind}: {n}")
    if doc.warnings:
        print(f"  avisos: {len(doc.warnings)}")
        for w in doc.warnings[:5]:
            print(f"    - {w}")


def main() -> int:
    out = ROOT / "data" / "validation"
    out.mkdir(parents=True, exist_ok=True)

    section("1) Exemplos sintéticos — mini_v1 × mini_v2")
    old = load_document(ROOT / "examples" / "mini_v1.txt")
    new = load_document(ROOT / "examples" / "mini_v2.txt")
    report = diff_documents(old, new)
    patch = render_patch(report)
    (out / "mini.patch.txt").write_text(patch, encoding="utf-8")
    (out / "mini.diff.json").write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(patch)
    s = report.summary
    assert s.insert >= 1, "esperava inserção (novo art. 3 / inciso IV / §3º)"
    assert s.renumber >= 1 or s.move >= 1 or s.modify >= 1, "esperava renumeração ou modify"
    print("OK mini diff")

    section("2) Fragmento LC 95")
    report2 = diff_documents(
        load_document(ROOT / "examples" / "lc95_fragment_v1.txt"),
        load_document(ROOT / "examples" / "lc95_fragment_v2.txt"),
    )
    print(render_patch(report2))
    assert any(c.op == "insert" for c in report2.changes), "esperava Art. 9º-A inserido"
    print("OK lc95 fragment")

    section("3) LexML XML")
    lexml = load_document(ROOT / "examples" / "sample.lexml.xml")
    assert any(d.kind == "artigo" for d in lexml.devices)
    print(f"LexML: {len(lexml.devices)} dispositivos")
    print("OK lexml")

    section("4) Documentos reais (data/raw)")
    raw = ROOT / "data" / "raw"
    if not raw.exists():
        print("data/raw ausente — rode scripts/fetch_samples.py")
        return 1

    targets = [
        "lc95.html",
        "lei14133.html",
        "lei8666.html",
        "decreto9191.html",
        "cf88.html",
        "senado_lc95.html",
    ]
    for name in targets:
        path = raw / name
        if not path.exists():
            print(f"faltando {name}")
            continue
        show_stats(path)
        doc = load_document(path)
        arts = [d for d in doc.devices if d.kind == "artigo"]
        assert len(arts) >= 5, f"{name}: poucos artigos ({len(arts)})"
        # Serializa AST resumida
        summary = {
            "source": str(path),
            "epigrafe": doc.epigrafe,
            "devices": len(doc.devices),
            "artigos": len(arts),
            "kinds": dict(
                __import__("collections").Counter(d.kind for d in doc.devices)
            ),
        }
        (out / f"{path.stem}.stats.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    section("5) Diff real: LC 95 Planalto × Senado")
    a = raw / "lc95.html"
    b = raw / "senado_lc95.html"
    if a.exists() and b.exists():
        cross = diff_documents(load_document(a), load_document(b))
        (out / "lc95_planalto_vs_senado.diff.json").write_text(
            json.dumps(cross.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out / "lc95_planalto_vs_senado.patch.txt").write_text(
            render_patch(cross), encoding="utf-8"
        )
        print(render_patch(cross)[:2500])
        print("…")
        print(f"summary: {cross.summary}")
        print("OK diff LC95 fontes")

    section("6) Parse leis de licitações (sem diff completo — corpora grandes)")
    for name in ("lei8666.html", "lei14133.html", "cf88_compilado.html"):
        path = raw / name
        if not path.exists():
            continue
        doc = load_document(path)
        arts = sum(1 for d in doc.devices if d.kind == "artigo")
        print(f"{name}: {len(doc.devices)} dispositivos, {arts} artigos")
        assert arts >= 50, f"{name}: artigos insuficientes"

    section("Validação manual concluída")
    print(f"Artefatos em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
