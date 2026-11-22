"""Normalização tipográfica para parsing e fingerprints estáveis."""

from __future__ import annotations

import re
import unicodedata

_ORDINAL_FIX = re.compile(
    r"(?i)\b(art(?:igo)?\.?|§|par[aá]grafo)\s*(\d+)\s*[oº°]\b"
)
_ART_SPACE = re.compile(r"(?i)\b(art)\s*\.\s*")
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NL = re.compile(r"\n{3,}")
_SOFT_HYPHEN = "\u00ad"
_BOM = "\ufeff"


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def collapse_whitespace(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\xa0", " ").replace(_SOFT_HYPHEN, "")
    value = _MULTI_SPACE.sub(" ", value)
    lines = [line.strip() for line in value.split("\n")]
    return _MULTI_NL.sub("\n\n", "\n".join(lines)).strip()


def fix_planalto_ordinals(value: str) -> str:
    """Converte artefatos 'Art. 1 o' / '§ 2 o' em 'Art. 1º' / '§ 2º'."""

    def repl(match: re.Match[str]) -> str:
        head, number = match.group(1), match.group(2)
        if head.lower().startswith("art"):
            return f"Art. {number}º"
        if head.startswith("§"):
            return f"§ {number}º"
        return f"parágrafo {number}º"

    return _ORDINAL_FIX.sub(repl, value)


_DEVICE_START = re.compile(
    r"(?i)^(?:"
    r"art(?:igo)?\.?\s*\d|"
    r"§|"
    r"par[aá]grafo\s+(?:único|\d)|"
    r"[IVXLCDM]{1,8}\s*[-–—.]|"
    r"[a-z]\s*[\)\.]|"
    r"\d+\s*[\)\.]|"
    r"CAP[ÍI]TULO\b|T[ÍI]TULO\b|LIVRO\b|PARTE\b|Se[çc][ãa]o\b|Subse[çc][ãa]o\b|ANEXO\b|"
    r"DISPOSI[CÇ]|"
    r"LEI\b|DECRETO\b|MEDIDA\b|CONSTITUI|EMENDA\b|RESOLU|PROJETO\b|PLC?\b|PEC\b|"
    r"O\s+PRESIDENTE|A\s+PRESIDENTA|Fa[çc]o\s+saber|"
    r"Bras[íi]lia,|Rio de Janeiro,|S[ãa]o Paulo,"
    r")"
)

_HEADER_NOISE = re.compile(
    r"(?i)^(Presid[eê]ncia(\s+da\s+Rep[uú]blica)?|da Rep[uú]blica|Casa Civil|"
    r"Secretaria-Geral|Subchefia para Assuntos Jur[ií]dicos\.?|Mensagem de veto|"
    r"Vig[eê]ncia|Texto compilado|Texto para impress[aã]o|Imprensa Nacional|"
    r"\[Detalhes da Norma\]|Este texto não substitui o original publicado.+|"
    r"Lcp95|L14133|L8666consol|D9191|L\d{4,5}.*|"
    r"Constituicao-Compilado|Constitui[cç][aã]o-Compilado)$"
)


def reflow_legislative(value: str) -> str:
    """Une quebras moles de HTML (inciso 'I' + '- texto') sem fundir dispositivos."""
    lines = [ln.strip() for ln in value.split("\n")]
    out: list[str] = []
    for line in lines:
        if not line:
            if out and out[-1] != "":
                out.append("")
            continue
        if _HEADER_NOISE.match(line):
            continue
        # Remissão "art. 12" / palavra "caput" isolada de HTML quebrado.
        if out and out[-1] and re.match(r"^art\.?\s*\d", line, re.I) and not re.match(
            r"^Art\.?\s*\d", line
        ):
            out[-1] = f"{out[-1]} {line}"
            continue
        if out and out[-1] and re.fullmatch(r"(?i)caput[.,;:]?", line):
            out[-1] = f"{out[-1]} {line}"
            continue
        if out and out[-1] and line.startswith((",", ";")):
            out[-1] = f"{out[-1]}{line}"
            continue
        if out and out[-1] and not _DEVICE_START.match(line):
            prev = out[-1]
            alone_label = re.fullmatch(
                r"(?:[IVXLCDM]{1,8}|[a-z]|\d+|§|§\s*\d+[º°o]?)",
                prev.strip(),
                re.I,
            )
            incomplete_epigrafe = bool(
                re.match(r"(?i)^(?:LEI|DECRETO|MEDIDA|EMENDA|CONSTITUI|RESOLU|PORTARIA)", prev)
            ) and not re.search(r"\b\d{4}\b", prev)
            # Epígrafe / frase incompleta: junta continuação (ex.: "DE 1998").
            if (
                alone_label
                or not _DEVICE_START.match(prev)
                or incomplete_epigrafe
                or prev.endswith((",", ";", "de", "De", "DE", "no", "na", "do", "da"))
            ):
                out[-1] = f"{prev} {line}"
                continue
        out.append(line)
    return "\n".join(out)


def normalize_for_parse(value: str) -> str:
    value = value.replace(_BOM, "")
    value = unicodedata.normalize("NFC", value)
    value = fix_planalto_ordinals(value)
    value = _ART_SPACE.sub(r"\1. ", value)
    value = collapse_whitespace(value)
    value = reflow_legislative(value)
    value = fix_planalto_ordinals(value)  # de novo após juntar "§ 1" + "o"
    return value


def normalize_for_fingerprint(value: str) -> str:
    value = normalize_for_parse(value)
    value = strip_accents(value).lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[\"'“”‘’]", "", value)
    value = re.sub(r"[;:]+", ",", value)
    return value.strip(" .,;")


def tokenize(value: str) -> list[str]:
    cleaned = normalize_for_fingerprint(value)
    return [tok for tok in re.split(r"[^a-z0-9§]+", cleaned) if tok]
