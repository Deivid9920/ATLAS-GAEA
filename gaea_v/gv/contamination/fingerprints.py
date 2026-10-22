"""fingerprints: huella SHA-256 normalizada + índice de 8-gramas.

Contamination contract (C-01, anchor 9): the exact fingerprint is
sha256 over normalized text; the 8-gram index detects partial overlap
against the frozen holdout. Zero impacts are tolerated; a single hit
invalidates the round (fail-loud).
"""

from __future__ import annotations

import hashlib
import re

_NGRAM_DEFAULT = 8

_WS = re.compile(r"\s+")
_KEEP = re.compile(r"[^a-z0-9\s]")


def normalize(text: str) -> str:
    """Lowercase, strip non-alphanumerics, collapse whitespace."""
    return _WS.sub(" ", _KEEP.sub("", (text or "").lower())).strip()


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def ngrams(text: str, n: int = _NGRAM_DEFAULT) -> set:
    words = normalize(text).split()
    if len(words) < n:
        return set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def exact_hits(text: str, known_fps: set[str]) -> list[str]:
    fp = fingerprint(text)
    return [fp] if fp in known_fps else []


def ngram_hits(text: str, holdout_index: set, n: int = _NGRAM_DEFAULT
               ) -> list[str]:
    return sorted(ngrams(text, n) & holdout_index)


def build_holdout_index(holdout_texts: list[str],
                        n: int = _NGRAM_DEFAULT) -> set:
    index: set = set()
    for text in holdout_texts:
        index |= ngrams(text, n)
    return index
