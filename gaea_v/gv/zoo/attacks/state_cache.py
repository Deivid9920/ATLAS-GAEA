"""ZOO-5xx state/cache: misma cadena, contextos distintos; invalidación.

The attack surface is the memoized verdict (evaluate_cached): the
cache key binds the registry signature, so re-registering a verifier
must invalidate. Expected: the correct verdict per case. The capture
rule is property_holds: the attack fails only when a stale verdict is
served after the registry changed, or identical keys collide across
different contexts.

These attacks run INSIDE the worker process against the real
CompositeVerifier via the cache_probe op (the state lives in ATLAS's
process, read-only).
"""

from __future__ import annotations

_CASES = ("cache_hit_stable", "reregister_invalidates",
          "context_changes_key", "one_byte_mutation",
          "fresh_matches_cached")


def _zoo_501(seed: int) -> dict:
    return {"code": "def sum_list(xs):\n    return sum(xs)\n",
            "tests": "assert sum_list([1, 2]) == 3\n",
            "triplets": [], "case": "cache_hit_stable"}


def _zoo_502(seed: int) -> dict:
    return {"code": "def sum_list(xs):\n    return sum(xs)\n",
            "tests": "assert sum_list([1, 2]) == 3\n",
            "triplets": [], "case": "reregister_invalidates"}


def _zoo_503(seed: int) -> dict:
    return {"code": "def sum_list(xs):\n    return sum(xs)\n",
            "tests": "assert sum_list([1, 2]) == 3\n",
            "triplets": [], "case": "context_changes_key"}


def _zoo_504(seed: int) -> dict:
    return {"code": "def sum_list(xs):\n    return sum(xs)\n",
            "tests": "assert sum_list([1, 2]) == 3\n",
            "triplets": [], "case": "one_byte_mutation"}


def _zoo_505(seed: int) -> dict:
    return {"code": "def sum_list(xs):\n    return sum(xs)\n",
            "tests": "assert sum_list([1, 2]) == 3\n",
            "triplets": [], "case": "fresh_matches_cached"}


def _mk(aid: str, desc: str, seed: int, case: str) -> dict:
    return {"id": aid, "category": "state_cache", "description": desc,
            "generator": f"zoo.attacks.state_cache:_zoo_{aid[-3:]}",
            "seed": seed, "expected_verdict": "approve",
            "capture_rule": "property_holds", "allowed_verdicts": [],
            "clean_family": "sum_list",
            "case": case, "generate": globals()[
                f"_zoo_{aid[-3:]}"]}


attacks = [
    _mk("ZOO-501", "identical claim+context is served stably from "
         "cache", 4221, _CASES[0]),
    _mk("ZOO-502", "re-registering a verifier changes the signature "
         "and invalidates memoized verdicts", 4222, _CASES[1]),
    _mk("ZOO-503", "same claim with different tests must not collide "
         "in the cache", 4223, _CASES[2]),
    _mk("ZOO-504", "a one-byte claim mutation produces a different "
         "cache key", 4224, _CASES[3]),
    _mk("ZOO-505", "fresh evaluate() never diverges from a clean cache "
         "hit", 4225, _CASES[4]),
]
