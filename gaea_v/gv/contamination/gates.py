"""gates: gate de contaminación obligatorio, fail-loud.

Every round that generates data passes through require_clean(). A
missing sensor (no holdout index supplied) invalidates the round:
sensor ausente no es sensor conforme.
"""

from __future__ import annotations

from gv.contamination.fingerprints import exact_hits, ngram_hits


class ContaminationError(RuntimeError):
    """One hit is one hit too many; the round dies here."""


class SensorMissingError(RuntimeError):
    pass


def require_clean(text: str, holdout_index: set, known_fps: set,
                  n: int = 8, max_hits: int = 0) -> dict:
    if holdout_index is None or known_fps is None:
        raise SensorMissingError(
            "contamination sensor missing: round is invalid (a "
            "missing sensor is never a conforming sensor)")
    exact = exact_hits(text, known_fps)
    grams = ngram_hits(text, holdout_index, n)
    result = {"exact_hits": len(exact), "ngram_hits": len(grams),
              "status": "ok" if not exact and not grams else "hit"}
    if len(exact) > max_hits or len(grams) > max_hits:
        raise ContaminationError(
            f"contamination gate fired: exact={len(exact)} "
            f"ngram={len(grams)} (max_hits={max_hits}); round invalid")
    return result
