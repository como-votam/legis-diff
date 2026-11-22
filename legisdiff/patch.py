"""Patches legíveis em estilo unified diff por dispositivo."""

from __future__ import annotations

from difflib import unified_diff

from legisdiff.models import Change, DiffReport

_OP_GLYPH = {
    "insert": "+",
    "delete": "-",
    "modify": "~",
    "move": ">",
    "renumber": "#",
    "revoke": "x",
    "equal": "=",
}


def _short(text: str | None, limit: int = 120) -> str:
    if not text:
        return ""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _path_pair(change: Change) -> str:
    if change.old_path and change.new_path and change.old_path != change.new_path:
        return f"{change.old_path} → {change.new_path}"
    return change.new_path or change.old_path or "?"


def format_change_line(change: Change) -> str:
    glyph = _OP_GLYPH.get(change.op, "?")
    kind = change.kind or "?"
    if change.op == "insert":
        return f"{glyph} INSERT {kind} {change.new_path}: {_short(change.new_text)}"
    if change.op == "delete":
        return f"{glyph} DELETE {kind} {change.old_path}: {_short(change.old_text)}"
    if change.op == "modify":
        sim = f"{change.similarity:.0%}" if change.similarity is not None else "?"
        return (
            f"{glyph} MODIFY {kind} {_path_pair(change)} (sim={sim})\n"
            f"    - {_short(change.old_text)}\n"
            f"    + {_short(change.new_text)}"
        )
    if change.op == "renumber":
        return (
            f"{glyph} RENUMBER {kind} {change.old_path} → {change.new_path}"
            + (f" ({change.reason})" if change.reason else "")
        )
    if change.op == "move":
        return f"{glyph} MOVE {kind} {change.old_path} → {change.new_path}"
    if change.op == "revoke":
        return f"{glyph} REVOKE {kind} {change.new_path or change.old_path}"
    return f"{glyph} EQUAL {kind} {change.old_path}"


def render_patch(report: DiffReport, *, context_unified: bool = True) -> str:
    lines: list[str] = []
    s = report.summary
    lines.append("Legis Diff — patch estrutural")
    if report.old_source or report.new_source:
        lines.append(f"--- {report.old_source or 'old'}")
        lines.append(f"+++ {report.new_source or 'new'}")
    lines.append(
        "resumo: "
        f"+{s.insert} -{s.delete} ~{s.modify} #{s.renumber} >{s.move} x{s.revoke} "
        f"(={s.equal} inalterados; dispositivos {s.devices_old}→{s.devices_new})"
    )
    lines.append("")

    meaningful = report.meaningful
    if not meaningful:
        lines.append("(sem mudanças estruturais)")
        return "\n".join(lines) + "\n"

    for change in meaningful:
        lines.append(format_change_line(change))
        if (
            context_unified
            and change.op == "modify"
            and change.old_text is not None
            and change.new_text is not None
        ):
            old_lines = change.old_text.splitlines() or [change.old_text]
            new_lines = change.new_text.splitlines() or [change.new_text]
            udiff = list(
                unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=change.old_path or "old",
                    tofile=change.new_path or "new",
                    lineterm="",
                )
            )
            if udiff:
                lines.extend(f"    {row}" for row in udiff)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
