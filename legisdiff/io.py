"""Leitura/escrita canônica de JSON e carregamento de documentos."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from legisdiff.html import html_to_text
from legisdiff.lexml import parse_lexml
from legisdiff.models import DiffReport, Document
from legisdiff.parser import parse_text


def canonical(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    def encode(obj: Any) -> Any:
        if isinstance(obj, BaseModel):
            return obj.model_dump(mode="json")
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(f"Tipo não canônico: {type(obj)}")

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=encode,
    ).encode("utf-8")


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, canonical(value) + b"\n")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_text(path: Path, content: str) -> None:
    atomic_write(path, content.encode("utf-8"))


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "iso-8859-1", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_document(path: Path) -> Document:
    """Detecta texto, HTML ou LexML XML e devolve Document."""
    raw = read_text(path)
    suffix = path.suffix.lower()
    head = raw.lstrip()[:280].lower()

    if suffix in {".xml", ".lexml"} or "<lexml" in head or "<norma" in head or "<articulacao" in head:
        return parse_lexml(raw, source=str(path))
    if (
        suffix in {".html", ".htm"}
        or head.startswith("<!doctype")
        or head.startswith("<html")
        or "<html" in head[:200]
        or "charset=" in head
    ):
        text = html_to_text(raw)
        return parse_text(text, source=str(path))
    return parse_text(raw, source=str(path))


def dump_document(doc: Document) -> dict[str, Any]:
    return doc.model_dump(mode="json")


def dump_report(report: DiffReport) -> dict[str, Any]:
    return report.model_dump(mode="json")
