"""Cálculo do diff estrutural/semântico entre duas versões."""

from __future__ import annotations

from legisdiff.identifiers import deep_text
from legisdiff.matcher import match_forests
from legisdiff.models import Change, DiffReport, DiffSummary, Document, Node, TextSpan
from legisdiff.parser import parse_text
from legisdiff.similarity import device_similarity

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


def _node_text(node: Node) -> str:
    if node.kind in _CONTAINER_KINDS:
        return deep_text(node)
    parts = [node.title or "", node.text or ""]
    return " ".join(p for p in parts if p).strip()


def diff_documents(
    old: Document,
    new: Document,
    *,
    include_equal: bool = False,
    modify_threshold: float = 0.55,
) -> DiffReport:
    matches = match_forests(
        old.devices,
        new.devices,
        modify_threshold=modify_threshold,
    )
    changes: list[Change] = []
    summary = DiffSummary(
        devices_old=len([d for d in old.devices if d.kind != "texto"]),
        devices_new=len([d for d in new.devices if d.kind != "texto"]),
    )

    for match in matches:
        relation = match.relation
        if relation == "equal":
            summary.equal += 1
            if not include_equal:
                continue
        elif relation == "insert":
            summary.insert += 1
        elif relation == "delete":
            summary.delete += 1
        elif relation == "modify":
            summary.modify += 1
        elif relation == "move":
            summary.move += 1
        elif relation == "renumber":
            summary.renumber += 1
        elif relation == "revoke":
            summary.revoke += 1

        old_node, new_node = match.old, match.new

        # Revogação detectada a posteriori (modify/equal com marca nova)
        if (
            relation in {"modify", "equal", "renumber", "move"}
            and old_node is not None
            and new_node is not None
            and not old_node.revoked
            and new_node.revoked
        ):
            if relation == "modify":
                summary.modify -= 1
            elif relation == "equal":
                summary.equal -= 1
            elif relation == "renumber":
                summary.renumber -= 1
            elif relation == "move":
                summary.move -= 1
            summary.revoke += 1
            relation = "revoke"

        text_diff = None
        if (
            old_node is not None
            and new_node is not None
            and relation in {"modify", "revoke"}
        ):
            text_diff = TextSpan(
                before=_node_text(old_node),
                after=_node_text(new_node),
                similarity=match.similarity
                if match.similarity
                else device_similarity(_node_text(old_node), _node_text(new_node)),
            )

        reason = None
        if relation == "renumber" and old_node and new_node:
            reason = f"renumerado de {old_node.label} para {new_node.label}"
        elif relation == "move" and old_node and new_node:
            reason = f"movido de {old_node.path} para {new_node.path}"
        elif relation == "revoke":
            reason = "dispositivo marcado como revogado/vetado"

        changes.append(
            Change(
                op=relation,  # type: ignore[arg-type]
                kind=(new_node or old_node).kind if (new_node or old_node) else None,
                old_id=old_node.id if old_node else None,
                new_id=new_node.id if new_node else None,
                old_path=old_node.path if old_node else None,
                new_path=new_node.path if new_node else None,
                old_label=old_node.label if old_node else None,
                new_label=new_node.label if new_node else None,
                old_text=_node_text(old_node) if old_node else None,
                new_text=_node_text(new_node) if new_node else None,
                similarity=match.similarity if relation != "insert" else None,
                reason=reason,
                text_diff=text_diff,
            )
        )

    # Ordena: deletes, inserts, modifies, renumbers, moves, equals
    order = {"delete": 0, "revoke": 1, "insert": 2, "modify": 3, "renumber": 4, "move": 5, "equal": 6}
    changes.sort(key=lambda c: (order.get(c.op, 9), c.old_path or c.new_path or ""))

    return DiffReport(
        summary=summary,
        changes=changes,
        old_source=old.source,
        new_source=new.source,
        options={
            "include_equal": include_equal,
            "modify_threshold": modify_threshold,
        },
    )


def diff_texts(
    old_text: str,
    new_text: str,
    *,
    old_source: str | None = None,
    new_source: str | None = None,
    include_equal: bool = False,
    modify_threshold: float = 0.55,
) -> DiffReport:
    old_doc = parse_text(old_text, source=old_source)
    new_doc = parse_text(new_text, source=new_source)
    return diff_documents(
        old_doc,
        new_doc,
        include_equal=include_equal,
        modify_threshold=modify_threshold,
    )
