"""Extração de texto articulado a partir de HTML (Planalto, Casa Civil, Senado)."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, NavigableString, Tag

from legisdiff.normalize import collapse_whitespace, fix_planalto_ordinals

_BLOCK_TAGS = {
    "p",
    "div",
    "br",
    "li",
    "tr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "section",
    "article",
    "header",
    "footer",
    "td",
}

_STRIP_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "nav",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "aside",
}

_STRIP_ID_CLASS = re.compile(
    r"(?i)(menu|nav|navbar|breadcrumb|footer|header-topo|cookie|"
    r"acessibilidade|toolbar|share|social|sidebar|banner|busca|search|"
    r"rodape|topo-portal|skip|pular)"
)


def _strip_noise(soup: BeautifulSoup) -> None:
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        if not isinstance(tag, Tag):
            continue
        attrs = tag.attrs or {}
        identity = " ".join(
            [
                str(attrs.get("id") or ""),
                " ".join(str(c) for c in (attrs.get("class") or [])),
                str(attrs.get("role") or ""),
            ]
        )
        if identity and _STRIP_ID_CLASS.search(identity):
            tag.decompose()


def _pick_root(soup: BeautifulSoup) -> Tag | BeautifulSoup:
    # Planalto/CF: HTML malformado com múltiplos <html> ou artigos fora do <body>.
    scopes: list[Tag] = [t for t in soup.find_all("html") if isinstance(t, Tag)]
    if soup.body and isinstance(soup.body, Tag):
        scopes.append(soup.body)
    scopes.append(soup)  # type: ignore[arg-type]

    best_scope: Tag | BeautifulSoup = soup
    best_scope_len = 0
    for scope in scopes:
        length = len(scope.get_text(" ", strip=True))
        if length > best_scope_len:
            best_scope = scope
            best_scope_len = length

    candidates: list[Tag] = []
    if isinstance(best_scope, Tag):
        search_root = best_scope
    else:
        search_root = soup
    for found in (
        search_root.find_all(id=re.compile(r"(?i)content|conteudo|texto|materia|norma")),
        search_root.find_all("article"),
        search_root.find_all("main"),
        search_root.find_all(class_=re.compile(r"(?i)content|conteudo|textoArtigo|texto-norma")),
    ):
        candidates.extend(t for t in found if isinstance(t, Tag))
    best: Tag | None = None
    best_len = 0
    for candidate in candidates:
        text_len = len(candidate.get_text(" ", strip=True))
        if text_len > best_len:
            best = candidate
            best_len = text_len
    if best is not None and best_len >= max(4000, int(best_scope_len * 0.5)):
        return best
    return best_scope


def _emit_blocks(node: Tag | NavigableString | BeautifulSoup, out: list[str]) -> None:
    if isinstance(node, NavigableString):
        text = str(node)
        if text.strip():
            out.append(text)
        return
    if not isinstance(node, (Tag, BeautifulSoup)):
        return
    name = (node.name or "").lower() if isinstance(node, Tag) else ""
    if name == "br":
        out.append("\n")
        return
    if name in _BLOCK_TAGS:
        out.append("\n")
    for child in node.children:
        _emit_blocks(child, out)  # type: ignore[arg-type]
    if name in _BLOCK_TAGS:
        out.append("\n")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    _strip_noise(soup)
    root = _pick_root(soup)
    chunks: list[str] = []
    _emit_blocks(root, chunks)
    text = "".join(chunks)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = collapse_whitespace(text)
    text = fix_planalto_ordinals(text)
    return text
