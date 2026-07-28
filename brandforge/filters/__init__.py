"""Name quality filters: length + pronunciation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from brandforge.generators import GeneratedName

# Awkward / hard-to-say patterns for English-leaning startup names
_HARD_CLUSTERS = re.compile(
    r"(?:[^aeiouy]{4,}|qx|xq|zx|xz|vx|xv|kx|xk|jx|xj|bx|xb|mxz|zzz|ttt|kkk)",
    re.IGNORECASE,
)
_TRIPLE_LETTER = re.compile(r"(.)\1\1", re.IGNORECASE)
_BAD_START = re.compile(r"^(?:ng|nk|mb|rl|sz|ts|ps|pt|kn|wr)", re.IGNORECASE)
_BAD_END = re.compile(r"(?:bh|dh|gh|kh|qh|xh|zh|aa|ee|ii|oo|uu|yy)$", re.IGNORECASE)
_VOWEL = set("aeiouy")


@dataclass(frozen=True, slots=True)
class FilterResult:
    name: GeneratedName
    passed: bool
    reasons: tuple[str, ...] = ()


def length_ok(name: str, min_len: int = 5, max_len: int = 10) -> bool:
    return min_len <= len(name) <= max_len


def pronunciation_score(name: str) -> float:
    """
    Higher is better (0–100). Heuristic for spoken clarity.
    """
    n = name.lower()
    score = 100.0

    if _HARD_CLUSTERS.search(n):
        score -= 40
    if _TRIPLE_LETTER.search(n):
        score -= 35
    if _BAD_START.match(n):
        score -= 25
    if _BAD_END.search(n):
        score -= 15

    vowels = sum(1 for c in n if c in _VOWEL)
    consonants = len(n) - vowels
    if vowels == 0:
        score -= 50
    else:
        ratio = consonants / max(vowels, 1)
        if ratio > 3.2:
            score -= 30
        elif ratio > 2.5:
            score -= 15

    # Prefer alternating-ish patterns
    alternations = 0
    for a, b in zip(n, n[1:]):
        if (a in _VOWEL) != (b in _VOWEL):
            alternations += 1
    alt_ratio = alternations / max(len(n) - 1, 1)
    if alt_ratio < 0.35:
        score -= 20
    elif alt_ratio > 0.55:
        score += 5

    # Soft endings feel more brandable
    if n.endswith(("a", "o", "io", "ia", "ly", "ix", "us", "um", "on", "ora", "ivo")):
        score += 8

    return max(0.0, min(100.0, score))


def is_pronounceable(name: str, min_score: float = 55.0) -> bool:
    return pronunciation_score(name) >= min_score


def filter_length(
    names: list[GeneratedName],
    *,
    min_len: int = 5,
    max_len: int = 10,
) -> list[GeneratedName]:
    return [n for n in names if length_ok(n.name, min_len, max_len)]


def filter_pronunciation(
    names: list[GeneratedName],
    *,
    min_score: float = 55.0,
) -> list[GeneratedName]:
    scored = [(n, pronunciation_score(n.name)) for n in names]
    scored = [(n, s) for n, s in scored if s >= min_score]
    scored.sort(key=lambda t: t[1], reverse=True)
    return [n for n, _ in scored]


def apply_basic_filters(
    names: list[GeneratedName],
    *,
    min_len: int = 5,
    max_len: int = 10,
    min_pronunciation: float = 55.0,
) -> list[GeneratedName]:
    """Length → pronunciation pipeline."""
    after_length = filter_length(names, min_len=min_len, max_len=max_len)
    return filter_pronunciation(after_length, min_score=min_pronunciation)
