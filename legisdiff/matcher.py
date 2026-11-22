"""Correspondência entre árvores com tratamento de renumeração e movimentação."""

from __future__ import annotations

from dataclasses import dataclass

from legisdiff.identifiers import deep_text
from legisdiff.models import Node, NodeKind
from legisdiff.similarity import best_matches, device_similarity

# Kinds compared as "devices" in the structural diff.
DIFF_KINDS: set[NodeKind] = {
    "epigrafe",
    "ementa",
    "preambulo",
    "parte",
    "livro",
    "titulo",
    "capitulo",
    "secao",
    "subsecao",
    "agrupamento",
    "artigo",
    "caput",
    "paragrafo",
    "inciso",
    "alinea",
    "item",
    "fechamento",
    "anexo",
}

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


@dataclass
class Match:
    old: Node | None
    new: Node | None
    similarity: float
    relation: str  # equal | modify | renumber | move | insert | delete


def _device_text(node: Node) -> str:
    if node.kind in _CONTAINER_KINDS:
        return deep_text(node)
    parts = [node.title or "", node.text or ""]
    return " ".join(p for p in parts if p).strip()


def _parent_path(path: str) -> str:
    if "/" not in path:
        return ""
    return path.rsplit("/", 1)[0]


def _label_segment(path: str) -> str:
    return path.rsplit("/", 1)[-1] if path else path


def _classify_path_change(old: Node, new: Node) -> str:
    """Distingue renumeração (mesmo pai lógico) de move (pai diferente)."""
    old_parent = _parent_path(old.path)
    new_parent = _parent_path(new.path)
    if old.path == new.path:
        return "same"
    # Artigo renumerado: path inteiro muda só no segmento art.N
    if old.kind == new.kind == "artigo":
        return "renumber" if old.label != new.label else "same"
    # Filho cujo path mudou porque o artigo pai foi renumerado
    if _label_segment(old.path) == _label_segment(new.path) and old_parent != new_parent:
        # Se só o ancestral mudou de número, trata como renumber em cascata
        old_segs = old.path.split("/")
        new_segs = new.path.split("/")
        if len(old_segs) == len(new_segs):
            diffs = [i for i, (a, b) in enumerate(zip(old_segs, new_segs, strict=True)) if a != b]
            if len(diffs) == 1 and old_segs[diffs[0]].split(".")[0] == new_segs[diffs[0]].split(".")[
                0
            ]:
                return "renumber"
        return "move"
    if old_parent == new_parent and old.label != new.label:
        return "renumber"
    if old_parent != new_parent:
        return "move"
    return "renumber"


def match_forests(
    old_nodes: list[Node],
    new_nodes: list[Node],
    *,
    modify_threshold: float = 0.55,
) -> list[Match]:
    """
    Algoritmo em fases:

    1. Fingerprint único → equal/renumber/move
    2. Mesmo path estrutural → equal/modify
    3. Similaridade por kind → modify/renumber/move
    4. Restantes → insert/delete
    """
    old = [n for n in old_nodes if n.kind in DIFF_KINDS]
    new = [n for n in new_nodes if n.kind in DIFF_KINDS]
    old_by_id = {n.id: n for n in old}
    new_by_id = {n.id: n for n in new}

    matched_old: set[str] = set()
    matched_new: set[str] = set()
    matches: list[Match] = []

    def register(o: Node | None, n: Node | None, sim: float, relation: str) -> None:
        if o is not None:
            matched_old.add(o.id)
        if n is not None:
            matched_new.add(n.id)
        matches.append(Match(old=o, new=n, similarity=sim, relation=relation))

    # --- Fase 1: fingerprints únicos -----------------------------------------
    fp_old: dict[str, list[Node]] = {}
    fp_new: dict[str, list[Node]] = {}
    for node in old:
        fp_old.setdefault(node.fingerprint, []).append(node)
    for node in new:
        fp_new.setdefault(node.fingerprint, []).append(node)

    for fp, olds in fp_old.items():
        news = fp_new.get(fp, [])
        if len(olds) == 1 and len(news) == 1:
            o, n = olds[0], news[0]
            if o.id in matched_old or n.id in matched_new:
                continue
            if o.kind != n.kind:
                continue
            sim = 1.0
            if o.path == n.path and _device_text(o) == _device_text(n):
                register(o, n, sim, "equal")
            else:
                change = _classify_path_change(o, n)
                if change == "same":
                    register(o, n, sim, "equal")
                elif change == "renumber":
                    register(o, n, sim, "renumber")
                else:
                    register(o, n, sim, "move")

    # --- Fase 2: mesmo id/path -----------------------------------------------
    for oid, o in old_by_id.items():
        if oid in matched_old:
            continue
        n = new_by_id.get(oid)
        if n is None or n.id in matched_new:
            continue
        if o.kind != n.kind:
            continue
        sim = device_similarity(_device_text(o), _device_text(n))
        if o.fingerprint == n.fingerprint or sim >= 0.97:
            register(o, n, max(sim, 0.97), "equal")
        elif n.revoked and not o.revoked:
            # Mesmo path com marca explícita de revogação/veto.
            register(o, n, sim, "revoke")
        elif sim >= modify_threshold:
            if o.kind in _CONTAINER_KINDS:
                # Mesmo path: o delta textual fica nos filhos (caput/§/inciso).
                register(o, n, sim, "equal")
            else:
                register(o, n, sim, "modify")
        elif o.kind in _CONTAINER_KINDS and n.revoked:
            register(o, n, sim, "revoke")
        # se similaridade baixa, deixa para fases seguintes / delete+insert

    # --- Fase 3: similaridade por kind ---------------------------------------
    kinds = sorted({n.kind for n in old + new})
    for kind in kinds:
        left = [
            (n.id, _device_text(n))
            for n in old
            if n.kind == kind and n.id not in matched_old
        ]
        right = [
            (n.id, _device_text(n))
            for n in new
            if n.kind == kind and n.id not in matched_new
        ]
        if not left or not right:
            continue
        # Artigos e agrupamentos pedem limiar um pouco maior
        thr = 0.62 if kind in {"artigo", "caput", "paragrafo"} else modify_threshold
        for lid, rid, score in best_matches(left, right, threshold=thr):
            o, n = old_by_id[lid], new_by_id[rid]
            path_change = _classify_path_change(o, n)
            identical = o.fingerprint == n.fingerprint or score >= 0.97
            if path_change == "move":
                # Move estrutural; deltas de texto ficam nos filhos quando houver.
                register(o, n, score, "move")
            elif path_change == "renumber":
                register(o, n, score, "renumber")
            elif identical:
                register(o, n, score, "equal")
            else:
                register(o, n, score, "modify")

    # --- Fase 4: insert / delete ---------------------------------------------
    for o in old:
        if o.id not in matched_old:
            register(o, None, 0.0, "delete")
    for n in new:
        if n.id not in matched_new:
            register(None, n, 0.0, "insert")

    return matches
