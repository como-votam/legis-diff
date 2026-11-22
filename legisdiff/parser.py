"""Parser da técnica legislativa brasileira (LC 95/1998) → AST."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from legisdiff.identifiers import assign_ids
from legisdiff.models import Document, Node, NodeKind
from legisdiff.normalize import normalize_for_parse
from legisdiff.numbering import (
    parse_alinea,
    parse_article_number,
    parse_inciso,
    parse_item,
    parse_paragraph_number,
)

# --- padrões de linha -------------------------------------------------------

# "Art." / "Artigo" com maiúscula = dispositivo. "art. 59" minúsculo = remissão.
_RE_ARTIGO = re.compile(
    r"^(?:Art\.?\s*|ART\.?\s*|Artigo\s+|ARTIGO\s+)(\d+[º°o]?(?:\s*-\s*[A-Za-z])?)\s*[.\-–—:]?\s*(.*)$"
)
_RE_PARAGRAFO = re.compile(
    r"(?i)^(?:§+\s*(\d+[º°o]?)|(par[aá]grafo\s+único)|"
    r"(par[aá]grafo\s+(\d+[º°o]?)))\s*[.\-–—:]?\s*(.*)$"
)
_RE_INCISO = re.compile(r"^(?P<label>[IVXLCDM]{1,8})\s*[-–—.]\s*(?P<body>.*)$")
_RE_ALINEA = re.compile(r"^(?P<label>[a-z])\s*[\)\.]\s*(?P<body>.*)$")
_RE_ITEM = re.compile(r"^(?P<label>\d+)\s*[\)\.]\s*(?P<body>.*)$")

_RE_PARTE = re.compile(
    r"(?i)^(?:PARTE\s+(?P<label>[IVXLCDM]+|GERAL|ESPECIAL|[A-ZÇÃÕÁÉÍÓÚ ]+))"
    r"(?:\s*[-–—]\s*(?P<title>.+))?$"
)
_RE_LIVRO = re.compile(
    r"(?i)^LIVRO\s+(?P<label>[IVXLCDM]+|\d+)(?:\s*[-–—]\s*(?P<title>.+))?$"
)
_RE_TITULO = re.compile(
    r"(?i)^T[ÍI]TULO\s+(?P<label>[IVXLCDM]+|\d+)(?:\s*[-–—]\s*(?P<title>.+))?$"
)
_RE_CAPITULO = re.compile(
    r"(?i)^CAP[ÍI]TULO\s+(?P<label>[IVXLCDM]+|\d+)(?:\s*[-–—]\s*(?P<title>.+))?$"
)
_RE_SECAO = re.compile(
    r"(?i)^Se[çc][ãa]o\s+(?P<label>[IVXLCDM]+|\d+)(?:\s*[-–—]\s*(?P<title>.+))?$"
)
_RE_SUBSECAO = re.compile(
    r"(?i)^Subse[çc][ãa]o\s+(?P<label>[IVXLCDM]+|\d+)(?:\s*[-–—]\s*(?P<title>.+))?$"
)
_RE_AGRUPAMENTO = re.compile(
    r"(?i)^(?P<title>DISPOSI[CÇ][OÕ]ES\s+"
    r"(?:PRELIMINARES|GERAIS|FINAIS|TRANSIT[OÓ]RIAS|FINAIS\s+E\s+TRANSIT[OÓ]RIAS)"
    r"|DISPOSI[CÇ][AÃ]O\s+TRANSIT[OÓ]RIA)$"
)
_RE_DA_GROUP = re.compile(
    r"^(?P<title>D[ao]s?\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-Za-zÁÉÍÓÚÂÊÔÃÕÇáéíóúâêôãõç ]{2,80})$"
)
_RE_FECHAMENTO = re.compile(
    r"(?i)^(?:Bras[íi]lia|Rio de Janeiro|S[ãa]o Paulo),\s*.*\d{4}.*$"
)
_RE_PREAMBULO = re.compile(
    r"(?i)^(?:O\s+PRESIDENTE\s+DA\s+REP[UÚ]BLICA|A\s+PRESIDENTA\s+DA\s+REP[UÚ]BLICA|"
    r"Fa[çc]o\s+saber|O\s+CONGRESSO\s+NACIONAL|"
    r"O\s+GOVERNADOR|A\s+ASSEMBL[EI]IA)"
)
_RE_EPIGRAFE = re.compile(
    r"(?i)^(?:LEI\s+(?:COMPLEMENTAR\s+)?N[ºO°\.]*\s*\d+|DECRETO(?:-LEI)?\s+N|"
    r"MEDIDA\s+PROVIS[OÓ]RIA\s+N|CONSTITUI[CÇ][AÃ]O(?:\s+DA\s+REP[UÚ]BLICA)?|"
    r"EMENDA\s+CONSTITUCIONAL|RESOLU[CÇ][AÃ]O|PORTARIA|"
    r"PROJETO\s+DE\s+LEI|PLC?\s+N|PLP\s+N|PEC\s+N)"
)
_RE_ANEXO = re.compile(r"(?i)^ANEXO(?:\s+[IVXLCDM\d]+)?(?:\s*[-–—].*)?$")
_RE_REVOGADO = re.compile(r"(?i)\(?(?:revogad[oa]|vetado)\)?")
_RE_NOTE = re.compile(
    r"(?i)^\((?:inclu[íi]do|redação|revogad|vide|acrescentado|vig[eê]ncia).+\)$"
)
_RE_META_LINE = re.compile(
    r"(?i)^(?:Mensagem de veto|Vig[eê]ncia|Texto compilado|Texto para impress[aã]o|"
    r"Regulamento|Promulga[cç][aã]o parts? vetadas|Promulga[cç][aã]o partes vetadas|"
    r"\(Vide .+\)|\(Revogad[oa] .+\)|\(Vig[eê]ncia\))$"
)


@dataclass
class _Frame:
    node: Node
    kind: NodeKind


@dataclass
class _ParserState:
    root: Node
    stack: list[_Frame] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    epigrafe: str | None = None
    ementa: str | None = None
    seen_artigo: bool = False
    pending_ementa_lines: list[str] = field(default_factory=list)
    in_preamble: bool = False
    preamble_parts: list[str] = field(default_factory=list)

    def push(self, node: Node) -> None:
        self.stack.append(_Frame(node=node, kind=node.kind))

    def current(self) -> Node:
        return self.stack[-1].node if self.stack else self.root

    def pop_until(self, allowed: set[NodeKind]) -> None:
        while len(self.stack) > 1 and self.stack[-1].kind not in allowed:
            self.stack.pop()

    def attach(self, node: Node, parents: set[NodeKind]) -> None:
        self.pop_until(parents | {"documento"})
        parent = self.current()
        # Caput vive dentro do artigo; se o pai atual não for válido, sobe.
        if parent.kind not in parents and parent.kind != "documento":
            self.pop_until(parents | {"documento"})
            parent = self.current()
        parent.children.append(node)
        self.push(node)


_ARTICLE_PARENTS: set[NodeKind] = {
    "documento",
    "parte",
    "livro",
    "titulo",
    "capitulo",
    "secao",
    "subsecao",
    "agrupamento",
    "anexo",
}
_PARAGRAFO_PARENTS: set[NodeKind] = {"artigo"}
_INCISO_PARENTS: set[NodeKind] = {"artigo", "caput", "paragrafo"}
_ALINEA_PARENTS: set[NodeKind] = {"inciso", "caput", "paragrafo"}
_ITEM_PARENTS: set[NodeKind] = {"alinea", "inciso"}
_GROUP_PARENTS: set[NodeKind] = {
    "documento",
    "parte",
    "livro",
    "titulo",
    "capitulo",
    "secao",
    "anexo",
}


def _is_revoked(text: str) -> bool:
    return bool(_RE_REVOGADO.search(text))


def _append_text(node: Node, chunk: str) -> None:
    chunk = chunk.strip()
    if not chunk:
        return
    if node.text:
        node.text = f"{node.text} {chunk}".strip()
    else:
        node.text = chunk
    if _is_revoked(chunk):
        node.revoked = True


def _ensure_caput(state: _ParserState) -> Node | None:
    """Garante caput no artigo atual antes de anexar incisos ao caput."""
    state.pop_until({"artigo", "documento"})
    artigo = state.current()
    if artigo.kind != "artigo":
        return None
    for child in artigo.children:
        if child.kind == "caput":
            state.push(child)
            return child
    caput = Node(kind="caput", text=artigo.text)
    artigo.text = ""
    artigo.children.insert(0, caput)
    state.push(caput)
    return caput


def _flush_preamble(state: _ParserState) -> None:
    if not state.preamble_parts:
        return
    text = " ".join(state.preamble_parts).strip()
    node = Node(kind="preambulo", text=text)
    state.root.children.append(node)
    state.preamble_parts.clear()
    state.in_preamble = False


def _flush_ementa(state: _ParserState) -> None:
    if state.ementa or not state.pending_ementa_lines:
        return
    text = " ".join(state.pending_ementa_lines).strip()
    text = re.sub(r"(?i)\(\s*Vide [^)]+\)\s*", "", text)
    text = re.sub(r"(?i)\bVide\s+Emenda[^.]+\.?\s*", "", text)
    text = re.sub(r"(?i)\bVide\s+[^\n.]+\.?\s*", "", text)
    text = re.sub(r"(?i)\(\s*Revogad[oa] [^)]+\)\s*", "", text)
    text = re.sub(r"(?i)\(\s*Vig[eê]ncia\s*\)\s*", "", text)
    text = re.sub(
        r"(?i)\b(?:Vig[eê]ncia|Regulamento|Promulga[cç][aã]o partes vetadas|"
        r"Emendas Constitucionais(?:\s+de Revis[aã]o)?|"
        r"Ato das Disposi[cç][oõ]es Constitucionais Transit[oó]rias|"
        r"[ÍI]ndice Tem[aá]tico|Texto compilado)\b\s*",
        "",
        text,
    )
    text = re.sub(r"\s{2,}", " ", text).strip(" -–—")
    if text and len(text) >= 20:
        state.ementa = text
        state.root.children.append(Node(kind="ementa", text=text))
    state.pending_ementa_lines.clear()


def _handle_group(
    state: _ParserState, kind: NodeKind, label: str | None, title: str | None
) -> None:
    _flush_preamble(state)
    _flush_ementa(state)
    node = Node(kind=kind, label=label.upper() if label else None, title=title)
    parents = {
        "parte": {"documento", "anexo"},
        "livro": {"documento", "parte", "anexo"},
        "titulo": {"documento", "parte", "livro", "anexo"},
        "capitulo": {"documento", "parte", "livro", "titulo", "anexo"},
        "secao": {"documento", "parte", "livro", "titulo", "capitulo", "anexo"},
        "subsecao": {"documento", "parte", "livro", "titulo", "capitulo", "secao", "anexo"},
        "agrupamento": _GROUP_PARENTS,
        "anexo": {"documento"},
    }[kind]
    state.attach(node, parents)


def _continue_text(state: _ParserState, line: str) -> None:
    if state.in_preamble:
        state.preamble_parts.append(line)
        return
    if not state.seen_artigo and state.epigrafe and not state.ementa:
        # Linhas entre epígrafe e preâmbulo/artigos → ementa
        if _RE_PREAMBULO.match(line):
            _flush_ementa(state)
            state.in_preamble = True
            state.preamble_parts.append(line)
            return
        if not _RE_NOTE.match(line) and not _RE_META_LINE.match(line):
            state.pending_ementa_lines.append(line)
        return
    current = state.current()
    if current.kind in {
        "caput",
        "paragrafo",
        "inciso",
        "alinea",
        "item",
        "artigo",
        "preambulo",
        "fechamento",
        "texto",
    }:
        _append_text(current, line)
        return
    # Texto solto: anexa ao último dispositivo textual, se houver
    devices = state.root.iter_devices()
    for node in reversed(devices):
        if node.kind in {"caput", "paragrafo", "inciso", "alinea", "item", "artigo"}:
            _append_text(node, line)
            return
    state.warnings.append(f"Texto sem dispositivo: {line[:80]}")


def _parse_lines(lines: list[str]) -> _ParserState:
    root = Node(kind="documento")
    state = _ParserState(root=root)
    state.push(root)

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if _RE_NOTE.match(line) or _RE_META_LINE.match(line):
            current = state.current()
            if current.kind != "documento" and _RE_NOTE.match(line):
                current.notes.append(line.strip("() "))
            continue

        # Fechamento
        if _RE_FECHAMENTO.match(line):
            _flush_preamble(state)
            node = Node(kind="fechamento", text=line)
            state.attach(node, {"documento", "anexo"})
            continue

        # Anexo
        if _RE_ANEXO.match(line):
            label_match = re.search(r"(?i)ANEXO\s+([IVXLCDM\d]+)", line)
            title = None
            if "–" in line or "-" in line or "—" in line:
                title = re.split(r"[-–—]", line, maxsplit=1)[-1].strip() or None
            _handle_group(
                state,
                "anexo",
                label_match.group(1) if label_match else None,
                title,
            )
            continue

        # Agrupamentos hierárquicos (Parte → Subseção)
        matched_group = False
        for regex, kind in (
            (_RE_PARTE, "parte"),
            (_RE_LIVRO, "livro"),
            (_RE_TITULO, "titulo"),
            (_RE_CAPITULO, "capitulo"),
            (_RE_SECAO, "secao"),
            (_RE_SUBSECAO, "subsecao"),
        ):
            match = regex.match(line)
            if match:
                _handle_group(
                    state,
                    kind,  # type: ignore[arg-type]
                    match.group("label"),
                    match.groupdict().get("title"),
                )
                matched_group = True
                break
        if matched_group:
            continue

        # DISPOSIÇÕES… / Da Estruturação… como agrupamentos nomeados
        if _RE_AGRUPAMENTO.match(line):
            _handle_group(state, "agrupamento", None, line)
            continue
        if (
            _RE_DA_GROUP.match(line)
            and not line.endswith(".")
            and len(line.split()) <= 12
        ):
            _handle_group(state, "agrupamento", None, line)
            continue
        # Títulos nominativos curtos de decreto/regulamento
        if re.fullmatch(
            r"(?i)Objeto e [aâ]mbito de aplica[cç][aã]o|Dispositivos finais|Anexo",
            line,
        ):
            _handle_group(state, "agrupamento", None, line)
            continue
        if (
            not state.seen_artigo
            and line.isupper()
            and 3 <= len(line) <= 80
            and not _RE_EPIGRAFE.match(line)
            and not re.search(r"\d", line)
        ):
            _flush_ementa(state)
            _flush_preamble(state)
            _handle_group(state, "agrupamento", None, line)
            continue

        # Epígrafe (ignora títulos de arquivo / chrome do HTML)
        if (
            not state.seen_artigo
            and not state.epigrafe
            and _RE_EPIGRAFE.match(line)
            and "compilado" not in line.lower()
            and len(line) >= 12
        ):
            state.epigrafe = line
            state.root.children.append(Node(kind="epigrafe", text=line))
            continue
        if (
            not state.seen_artigo
            and not state.epigrafe
            and re.match(r"(?i)^CONSTITUI[CÇ][AÃ]O\b", line)
        ):
            state.epigrafe = line
            state.root.children.append(Node(kind="epigrafe", text=line))
            continue

        # Marcador "PREÂMBULO" (Constituição) ou fórmula clássica
        if not state.seen_artigo and re.fullmatch(r"(?i)PRE[ÂA]MBULO", line):
            _flush_ementa(state)
            state.in_preamble = True
            continue
        if not state.seen_artigo and _RE_PREAMBULO.match(line):
            _flush_ementa(state)
            state.in_preamble = True
            state.preamble_parts.append(line)
            continue
        if (
            not state.seen_artigo
            and state.in_preamble
            and not _RE_ARTIGO.match(line)
            and not _RE_TITULO.match(line)
            and not _RE_CAPITULO.match(line)
        ):
            state.preamble_parts.append(line)
            continue

        # Artigo
        art = _RE_ARTIGO.match(line)
        if art:
            _flush_preamble(state)
            _flush_ementa(state)
            state.seen_artigo = True
            label = parse_article_number(art.group(1))
            body = (art.group(2) or "").strip()
            node = Node(kind="artigo", label=label, revoked=_is_revoked(body))
            state.attach(node, _ARTICLE_PARENTS)
            if body:
                caput = Node(kind="caput", text=body, revoked=_is_revoked(body))
                node.children.append(caput)
                state.push(caput)
            continue

        # Parágrafo
        parag = _RE_PARAGRAFO.match(line)
        if parag and state.seen_artigo:
            if parag.group(2):  # parágrafo único
                label = "unico"
                body = (parag.group(5) or "").strip()
            elif parag.group(1):
                label = parse_paragraph_number(parag.group(1))
                body = (parag.group(5) or "").strip()
            else:
                label = parse_paragraph_number(parag.group(4) or parag.group(3) or "")
                body = (parag.group(5) or "").strip()
            node = Node(kind="paragrafo", label=label, text=body, revoked=_is_revoked(body))
            # Sai do caput/inciso e volta ao artigo
            state.pop_until({"artigo", "documento"})
            state.attach(node, _PARAGRAFO_PARENTS)
            continue

        # Inciso (romanos) — só após artigo
        inciso = _RE_INCISO.match(line)
        if inciso and state.seen_artigo:
            label = parse_inciso(inciso.group("label"))
            body = inciso.group("body").strip()
            # Se estamos em artigo sem caput formal, cria caput
            cur = state.current()
            if cur.kind == "artigo":
                _ensure_caput(state)
            elif cur.kind in {"alinea", "item", "inciso"}:
                # novo inciso sobe para caput/parágrafo/artigo
                state.pop_until({"caput", "paragrafo", "artigo", "documento"})
                if state.current().kind == "artigo":
                    _ensure_caput(state)
            node = Node(kind="inciso", label=label, text=body, revoked=_is_revoked(body))
            state.attach(node, _INCISO_PARENTS)
            continue

        # Alínea
        alinea = _RE_ALINEA.match(line)
        if alinea and state.seen_artigo:
            label = parse_alinea(alinea.group("label"))
            body = alinea.group("body").strip()
            state.pop_until({"inciso", "caput", "paragrafo", "artigo", "documento"})
            node = Node(kind="alinea", label=label, text=body, revoked=_is_revoked(body))
            state.attach(node, _ALINEA_PARENTS)
            continue

        # Item
        item = _RE_ITEM.match(line)
        if item and state.seen_artigo:
            # Evita confundir "1." de listas com início de frase em texto corrido:
            # item só é válido sob alínea/inciso.
            if state.current().kind in {"alinea", "inciso", "item"} or any(
                f.kind in {"alinea", "inciso"} for f in state.stack
            ):
                label = parse_item(item.group("label"))
                body = item.group("body").strip()
                state.pop_until({"alinea", "inciso", "documento"})
                node = Node(kind="item", label=label, text=body, revoked=_is_revoked(body))
                state.attach(node, _ITEM_PARENTS)
                continue

        _continue_text(state, line)

    _flush_preamble(state)
    _flush_ementa(state)
    return state


def parse_text(text: str, *, source: str | None = None) -> Document:
    """Converte texto legislativo articulado em `Document` com AST."""
    normalized = normalize_for_parse(text)
    lines = normalized.split("\n")
    state = _parse_lines(lines)
    assign_ids(state.root)
    return Document(
        source=source,
        format="text",
        epigrafe=state.epigrafe,
        ementa=state.ementa,
        root=state.root,
        warnings=state.warnings,
    )
