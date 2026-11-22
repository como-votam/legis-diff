"""Importação de documentos LexML XML para a AST do Legis Diff."""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from legisdiff.identifiers import assign_ids
from legisdiff.models import Document, Node, NodeKind
from legisdiff.numbering import (
    parse_alinea,
    parse_article_number,
    parse_inciso,
    parse_item,
    parse_paragraph_number,
)

_TAG_KIND: dict[str, NodeKind] = {
    "parte": "parte",
    "livro": "livro",
    "titulo": "titulo",
    "capitulo": "capitulo",
    "secao": "secao",
    "subsecao": "subsecao",
    "artigo": "artigo",
    "caput": "caput",
    "paragrafo": "paragrafo",
    "inciso": "inciso",
    "alinea": "alinea",
    "item": "item",
    "anexo": "anexo",
}


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1].lower()
    return tag.lower()


def _text_of(elem: ET.Element) -> str:
    parts: list[str] = []
    if elem.text and elem.text.strip():
        parts.append(elem.text.strip())
    for child in elem:
        name = _local(child.tag)
        if name in {"p", "span", "i", "b", "em", "strong", "a", "sup", "sub"}:
            parts.append(_text_of(child))
        if child.tail and child.tail.strip():
            parts.append(child.tail.strip())
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def _label_from(elem: ET.Element, kind: NodeKind) -> str | None:
    for attr in ("id", "nome", "rotulo", "label"):
        raw = elem.attrib.get(attr)
        if not raw:
            continue
        # ids LexML costumam ser art1, art1_cpt, art1_par1, art1_inc1...
        if kind == "artigo":
            m = re.search(r"(\d+[A-Za-z\-]*)", raw)
            return parse_article_number(m.group(1)) if m else raw
        if kind == "paragrafo":
            if "unico" in raw.lower() or "único" in raw.lower():
                return "unico"
            m = re.search(r"(\d+)", raw)
            return parse_paragraph_number(m.group(1)) if m else raw
        if kind == "inciso":
            m = re.search(r"([IVXLCDM]+|\d+)$", raw.upper())
            return parse_inciso(m.group(1)) if m else raw
        if kind == "alinea":
            m = re.search(r"([a-z])$", raw.lower())
            return parse_alinea(m.group(1)) if m else raw
        if kind == "item":
            m = re.search(r"(\d+)$", raw)
            return parse_item(m.group(1)) if m else raw
        return raw
    # fallback: primeiro texto curto tipo "Art. 1º"
    direct = (elem.text or "").strip()
    if kind == "artigo":
        m = re.match(r"(?i)art(?:igo)?\.?\s*(\d+[º°oA-Za-z\-]*)", direct)
        if m:
            return parse_article_number(m.group(1))
    return None


def _convert(elem: ET.Element) -> Node | None:
    kind = _TAG_KIND.get(_local(elem.tag))
    if kind is None:
        return None
    label = _label_from(elem, kind)
    text = ""
    children: list[Node] = []
    # Texto próprio: ignora filhos estruturais
    structural = set(_TAG_KIND)
    own_bits: list[str] = []
    if elem.text and elem.text.strip():
        own_bits.append(elem.text.strip())
    for child in elem:
        child_kind = _local(child.tag)
        if child_kind in structural:
            converted = _convert(child)
            if converted is not None:
                children.append(converted)
        else:
            bit = _text_of(child)
            if bit:
                own_bits.append(bit)
        if child.tail and child.tail.strip():
            own_bits.append(child.tail.strip())
    text = re.sub(r"\s+", " ", " ".join(own_bits)).strip()
    # Rotulos embutidos no texto ("Art. 1º ...") — remove prefixo se já temos label
    if kind == "artigo" and label:
        text = re.sub(r"(?i)^art(?:igo)?\.?\s*\d+[º°oA-Za-z\-]*\s*[.\-–—:]?\s*", "", text)
    if kind == "paragrafo" and label:
        text = re.sub(
            r"(?i)^(?:§+\s*\d+[º°o]?|par[aá]grafo\s+único)\s*[.\-–—:]?\s*",
            "",
            text,
        )
    node = Node(kind=kind, label=label, text=text, children=children)
    if re.search(r"(?i)revogad|vetado", text):
        node.revoked = True
    return node


def parse_lexml(xml_text: str, *, source: str | None = None) -> Document:
    root_xml = ET.fromstring(xml_text)
    doc_root = Node(kind="documento")
    epigrafe = None
    ementa = None
    warnings: list[str] = []

    # Percorre em busca de Articulacao / metadados comuns
    for elem in root_xml.iter():
        name = _local(elem.tag)
        if name in {"epigrafe", "identificacao"} and epigrafe is None:
            text = _text_of(elem)
            if text:
                epigrafe = text
                doc_root.children.append(Node(kind="epigrafe", text=text))
        elif name == "ementa" and ementa is None:
            text = _text_of(elem)
            if text:
                ementa = text
                doc_root.children.append(Node(kind="ementa", text=text))
        elif name == "preambulo":
            text = _text_of(elem)
            if text:
                doc_root.children.append(Node(kind="preambulo", text=text))

    articulacao = None
    for elem in root_xml.iter():
        if _local(elem.tag) == "articulacao":
            articulacao = elem
            break

    target = articulacao if articulacao is not None else root_xml
    for child in list(target):
        converted = _convert(child)
        if converted is not None:
            doc_root.children.append(converted)
        else:
            # tenta netos se o filho for container genérico
            for grandchild in list(child):
                converted = _convert(grandchild)
                if converted is not None:
                    doc_root.children.append(converted)

    if len(doc_root.children) == 0:
        warnings.append("LexML sem articulação reconhecível")

    assign_ids(doc_root)
    return Document(
        source=source,
        format="lexml",
        epigrafe=epigrafe,
        ementa=ementa,
        root=doc_root,
        warnings=warnings,
    )
