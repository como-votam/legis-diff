"""Identificadores estáveis por dispositivo e fingerprints de conteúdo."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from legisdiff.models import Node, NodeKind
from legisdiff.normalize import normalize_for_fingerprint

_KIND_PREFIX: dict[NodeKind, str] = {
    "epigrafe": "epig",
    "ementa": "ementa",
    "preambulo": "preamb",
    "parte": "parte",
    "livro": "livro",
    "titulo": "tit",
    "capitulo": "cap",
    "secao": "sec",
    "subsecao": "subsec",
    "agrupamento": "agr",
    "artigo": "art",
    "caput": "caput",
    "paragrafo": "p",
    "inciso": "inc",
    "alinea": "al",
    "item": "item",
    "fechamento": "fech",
    "anexo": "anexo",
    "texto": "txt",
    "documento": "doc",
}


def content_fingerprint(text: str) -> str:
    payload = normalize_for_fingerprint(text).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def deep_text(node: Node) -> str:
    """Texto do nó e descendentes — usado em contêineres (artigo, etc.)."""
    parts: list[str] = []
    if node.title:
        parts.append(node.title)
    if node.text:
        parts.append(node.text)
    for child in node.children:
        chunk = deep_text(child)
        if chunk:
            parts.append(chunk)
    return " ".join(parts).strip()


def segment_for(kind: NodeKind, label: str | None) -> str:
    prefix = _KIND_PREFIX.get(kind, kind)
    if kind == "caput" or label is None or label == "":
        return prefix
    if kind == "paragrafo" and label == "unico":
        return "p.unico"
    return f"{prefix}.{label}"


_CONTAINER_KINDS = {
    "artigo",
    "parte",
    "livro",
    "titulo",
    "capitulo",
    "secao",
    "subsecao",
    "agrupamento",
    "anexo",
}


def assign_ids(node: Node, parent_path: str = "", *, sibling_index: int = 0) -> None:
    """Atribui `path`, `id` e `fingerprint` em profundidade."""
    segment = segment_for(node.kind, node.label)
    path = segment if not parent_path else f"{parent_path}/{segment}"
    if node.kind == "documento":
        path = ""
    # Texto compilado pode repetir Art. 9º (redações sucessivas): desambiguar.
    if sibling_index > 0 and node.kind != "documento":
        path = f"{path}#{sibling_index + 1}"
    node.path = path
    node.id = path or "documento"
    # Contagem de segmentos entre irmãos para desambiguar labels repetidos
    seen: dict[str, int] = {}
    for child in node.children:
        child_seg = segment_for(child.kind, child.label)
        idx = seen.get(child_seg, 0)
        seen[child_seg] = idx + 1
        assign_ids(child, path, sibling_index=idx)
    own_text = node.text or node.title or ""
    if node.kind in _CONTAINER_KINDS:
        node.fingerprint = content_fingerprint(deep_text(node) or node.id)
    elif own_text.strip():
        node.fingerprint = content_fingerprint(own_text)
    else:
        child_fps = "".join(child.fingerprint for child in node.children)
        node.fingerprint = content_fingerprint(child_fps or node.id)


def relabel_tree(nodes: Iterable[Node]) -> None:
    for node in nodes:
        assign_ids(node)
