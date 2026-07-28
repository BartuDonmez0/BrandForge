"""Combinatorial + syllable name generation (targets 100k+ unique names)."""

from __future__ import annotations

import itertools
import random
import re
from dataclasses import dataclass
from typing import Final

from brandforge.config import (
    CATEGORY_PREFIXES,
    CATEGORY_SUFFIXES,
    DEFAULT_PREFIXES,
    DEFAULT_SUFFIXES,
    resolve_category,
)

# Phonetic syllable parts — large combinatorial space for brandable coinages
_ONSETS: Final[tuple[str, ...]] = (
    "b", "c", "d", "f", "g", "h", "j", "k", "l", "m", "n", "p", "r", "s", "t",
    "v", "w", "x", "z", "br", "bl", "cr", "cl", "dr", "fl", "fr", "gl", "gr",
    "kr", "kl", "pl", "pr", "qu", "sc", "sk", "sl", "sm", "sn", "sp", "st",
    "sw", "tr", "tw", "vr", "th", "ch", "sh", "ph", "ny", "my",
)
_NUCLEI: Final[tuple[str, ...]] = (
    "a", "e", "i", "o", "u", "y", "ae", "ai", "ao", "au", "ea", "ei", "eo",
    "ia", "ie", "io", "iu", "oa", "oe", "oi", "ou", "ua", "ue", "ui",
)
_CODAS: Final[tuple[str, ...]] = (
    "", "n", "r", "l", "s", "t", "x", "m", "d", "k", "z", "v",
)

_VOWELS = set("aeiouy")
_CONSONANTS = set("bcdfghjklmnpqrstvwxz")


@dataclass(frozen=True, slots=True)
class GeneratedName:
    name: str
    prefix: str
    suffix: str
    category: str | None = None


def _title_case(name: str) -> str:
    return name[:1].upper() + name[1:].lower()


def _blend(prefix: str, suffix: str) -> str:
    """Join roots with light vowel collision handling."""
    p, s = prefix.lower(), suffix.lower()
    if not p or not s:
        return p + s
    if p.endswith(s[:2]) and len(s) > 2:
        return p + s[2:]
    if p[-1] == s[0] and p[-1] in _VOWELS:
        return p + s[1:]
    if p[-1] in _CONSONANTS and s[0] in _CONSONANTS and p[-1] != s[0]:
        if p[-1] + s[0] in {"xl", "xr", "xk", "xq", "zx", "vx", "kx"}:
            return p + "i" + s
    return p + s


def _dedupe_preserve(names: list[GeneratedName]) -> list[GeneratedName]:
    seen: set[str] = set()
    out: list[GeneratedName] = []
    for item in names:
        key = item.name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _syllable(onset: str, nucleus: str, coda: str = "") -> str:
    return f"{onset}{nucleus}{coda}"


def generate_combinations(
    prefixes: tuple[str, ...] | list[str],
    suffixes: tuple[str, ...] | list[str],
    *,
    category: str | None = None,
    limit: int | None = None,
    seed: int | None = None,
) -> list[GeneratedName]:
    """Generate unique name combinations, shuffled when a seed is provided."""
    pairs = list(itertools.product(prefixes, suffixes))
    if seed is not None:
        rng = random.Random(seed)
        rng.shuffle(pairs)
    else:
        random.shuffle(pairs)

    results: list[GeneratedName] = []
    for prefix, suffix in pairs:
        raw = _blend(prefix, suffix)
        if not re.fullmatch(r"[a-z]+", raw):
            continue
        results.append(
            GeneratedName(
                name=_title_case(raw),
                prefix=prefix.lower(),
                suffix=suffix.lower(),
                category=category,
            )
        )
        if limit is not None and len(results) >= limit:
            break

    return _dedupe_preserve(results)


def _expand_with_syllables(
    *,
    prefixes: list[str],
    suffixes: list[str],
    category: str | None,
    need: int,
    seed: int,
    existing: set[str],
) -> list[GeneratedName]:
    """Fill remaining quota with 2–3 syllable coinages + root hybrids."""
    rng = random.Random(seed)
    out: list[GeneratedName] = []

    # Precompute a pool of short syllables
    syllables: list[str] = []
    for o, n, c in itertools.product(_ONSETS, _NUCLEI, _CODAS):
        syl = _syllable(o, n, c)
        if 2 <= len(syl) <= 4:
            syllables.append(syl)
    rng.shuffle(syllables)

    attempts = 0
    max_attempts = max(need * 8, 50_000)
    while len(out) < need and attempts < max_attempts:
        attempts += 1
        mode = rng.randrange(4)

        if mode == 0 and prefixes and suffixes:
            # Classic root blend (user model): Mer + ixa
            raw = _blend(rng.choice(prefixes), rng.choice(suffixes))
            prefix, suffix = raw[:3], raw[3:] or "x"
        elif mode == 1:
            # Two syllables
            a, b = rng.choice(syllables), rng.choice(syllables)
            raw = a + b
            prefix, suffix = a, b
        elif mode == 2:
            # Root + syllable suffix
            a = rng.choice(prefixes) if prefixes else rng.choice(syllables)
            b = rng.choice(syllables)
            raw = _blend(a, b)
            prefix, suffix = a, b
        else:
            # Three short syllables (trim if too long later via filter)
            parts = [rng.choice(syllables) for _ in range(3)]
            # Prefer shorter syllables for triples
            parts = [p for p in parts if len(p) <= 3] or parts[:2]
            if len(parts) < 2:
                continue
            raw = "".join(parts[:3])
            prefix, suffix = parts[0], "".join(parts[1:])

        if not re.fullmatch(r"[a-z]{4,12}", raw):
            continue
        if raw in existing:
            continue
        existing.add(raw)
        out.append(
            GeneratedName(
                name=_title_case(raw),
                prefix=prefix,
                suffix=suffix,
                category=category,
            )
        )

    return out


def generate_names(
    *,
    category: str | None = None,
    target_count: int = 100_000,
    extra_prefixes: list[str] | None = None,
    extra_suffixes: list[str] | None = None,
    seed: int | None = 42,
) -> list[GeneratedName]:
    """
    Build a large candidate pool.

    Starts with category/default root×suffix blends (Merixa, Lumivo, …),
    then expands with phonetic syllables until `target_count` unique names.
    """
    resolved = resolve_category(category)
    if resolved:
        prefixes = list(CATEGORY_PREFIXES[resolved])
        suffixes = list(CATEGORY_SUFFIXES[resolved])
        # Always mix in general brandable roots too
        prefixes.extend(DEFAULT_PREFIXES)
        suffixes.extend(DEFAULT_SUFFIXES)
    else:
        prefixes = list(DEFAULT_PREFIXES)
        suffixes = list(DEFAULT_SUFFIXES)
        resolved = None

    if extra_prefixes:
        prefixes.extend(p.lower() for p in extra_prefixes if p)
    if extra_suffixes:
        suffixes.extend(s.lower() for s in extra_suffixes if s)

    prefixes = list(dict.fromkeys(p.lower().strip() for p in prefixes if p.strip()))
    suffixes = list(dict.fromkeys(s.lower().strip() for s in suffixes if s.strip()))

    names = generate_combinations(
        prefixes,
        suffixes,
        category=resolved,
        limit=target_count,
        seed=seed,
    )

    if len(names) < target_count:
        mid_suffixes = (
            "a", "e", "i", "o", "u", "y", "en", "ar", "el", "or", "um",
            "ax", "ex", "ix", "ox", "ux", "an", "in", "on", "un",
        )
        more = generate_combinations(
            prefixes,
            mid_suffixes,
            category=resolved,
            limit=target_count - len(names),
            seed=(seed or 0) + 7,
        )
        names = _dedupe_preserve(names + more)

    if len(names) < target_count:
        existing = {n.name.lower() for n in names}
        extras = _expand_with_syllables(
            prefixes=prefixes,
            suffixes=suffixes,
            category=resolved,
            need=target_count - len(names),
            seed=(seed or 0) + 99,
            existing=existing,
        )
        names = _dedupe_preserve(names + extras)

    return names[:target_count]
