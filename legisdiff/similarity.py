"""Similaridade textual para correspondência de dispositivos modificados."""

from __future__ import annotations

from difflib import SequenceMatcher

from legisdiff.normalize import tokenize


def jaccard(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def sequence_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def device_similarity(text_a: str, text_b: str) -> float:
    """Combina overlap lexical e alinhamento de sequência."""
    ta, tb = tokenize(text_a), tokenize(text_b)
    jac = jaccard(ta, tb)
    if jac < 0.2:
        return jac
    seq = sequence_ratio(" ".join(ta), " ".join(tb))
    return 0.55 * jac + 0.45 * seq


def best_matches(
    left: list[tuple[str, str]],
    right: list[tuple[str, str]],
    *,
    threshold: float = 0.55,
) -> list[tuple[str, str, float]]:
    """
    Pareamento guloso 1:1 por similaridade.

    `left`/`right` são listas de (id, texto).
    """
    scored: list[tuple[float, str, str]] = []
    right_tokens = [(rid, rt, tokenize(rt), len(rt)) for rid, rt in right]
    for lid, lt in left:
        ltoks = tokenize(lt)
        llen = len(lt)
        if llen == 0 and not ltoks:
            continue
        for rid, rt, rtoks, rlen in right_tokens:
            if llen and rlen:
                ratio = llen / rlen if llen >= rlen else rlen / llen
                if ratio > 3.5:
                    continue
            score = device_similarity(lt, rt) if ltoks or rtoks else 0.0
            # Atalho: overlap lexical barato já abaixo do limiar
            if score < threshold:
                continue
            scored.append((score, lid, rid))
    scored.sort(reverse=True, key=lambda row: row[0])
    used_l: set[str] = set()
    used_r: set[str] = set()
    pairs: list[tuple[str, str, float]] = []
    for score, lid, rid in scored:
        if lid in used_l or rid in used_r:
            continue
        used_l.add(lid)
        used_r.add(rid)
        pairs.append((lid, rid, score))
    return pairs
