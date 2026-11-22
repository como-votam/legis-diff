"""Numeração legislativa: ordinais, romanos, alíneas e rótulos canônicos."""

from __future__ import annotations

import re

_ORDINAL_WORDS = {
    "primeiro": 1,
    "segundo": 2,
    "terceiro": 3,
    "quarto": 4,
    "quinto": 5,
    "sexto": 6,
    "setimo": 7,
    "sétimo": 7,
    "oitavo": 8,
    "nono": 9,
    "decimo": 10,
    "décimo": 10,
}

_ROMAN_MAP = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def roman_to_int(value: str) -> int | None:
    text = value.upper().strip()
    if not text or any(ch not in _ROMAN_MAP for ch in text):
        return None
    total = 0
    prev = 0
    for ch in reversed(text):
        current = _ROMAN_MAP[ch]
        if current < prev:
            total -= current
        else:
            total += current
            prev = current
    return total


def int_to_roman(value: int) -> str:
    pairs = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    out: list[str] = []
    n = value
    for arab, roman in pairs:
        while n >= arab:
            out.append(roman)
            n -= arab
    return "".join(out)


def parse_article_number(raw: str) -> str:
    """Normaliza '1º', '1o', '1°', '1-A', '1º-A' → '1' ou '1-A'."""
    text = raw.strip().upper().replace("º", "").replace("°", "").replace("O", "")
    text = text.replace(" ", "")
    match = re.fullmatch(r"(\d+)(?:-([A-Z]))?", text)
    if not match:
        cleaned = re.sub(r"[^0-9A-Z-]", "", text)
        return cleaned or raw.strip()
    base, letter = match.group(1), match.group(2)
    return f"{base}-{letter}" if letter else base


def parse_paragraph_number(raw: str) -> str:
    text = raw.strip().lower()
    if "unico" in text.replace("ú", "u") or text in {"único", "unico"}:
        return "unico"
    digits = re.search(r"(\d+)", text)
    if digits:
        return digits.group(1)
    word = re.sub(r"[^a-zà-ú]", "", text)
    if word in _ORDINAL_WORDS:
        return str(_ORDINAL_WORDS[word])
    return raw.strip()


def parse_inciso(raw: str) -> str:
    text = raw.strip().upper().rstrip(".")
    if roman_to_int(text) is not None:
        return text
    return text


def parse_alinea(raw: str) -> str:
    return raw.strip().lower().rstrip(").")


def parse_item(raw: str) -> str:
    digits = re.search(r"(\d+)", raw)
    return digits.group(1) if digits else raw.strip()


def article_sort_key(label: str) -> tuple[int, str]:
    match = re.fullmatch(r"(\d+)(?:-([A-Z]))?", label.upper())
    if not match:
        return (10**9, label)
    return (int(match.group(1)), match.group(2) or "")


def inciso_sort_key(label: str) -> int:
    value = roman_to_int(label)
    return value if value is not None else 10**9
