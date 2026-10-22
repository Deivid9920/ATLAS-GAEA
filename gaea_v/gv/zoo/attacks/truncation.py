"""ZOO-3xx truncation and boundary: cut code, early returns, edges.

Código cortado, returns tempranos y bordes vacíos/None/negativos. The
verifier must refuse approval when the candidate only survives the
happy path.
"""

from __future__ import annotations

import random

_FACT_SUM = {"subject": "sum_list", "predicate": "computes",
             "object": "total_of_integers"}


def _zoo_301(seed: int) -> dict:
    return {
        "code": "def sum_list(xs):\n    return sum(",
        "tests": "assert sum_list([1, 2]) == 3\n",
        "triplets": [_FACT_SUM],
        "note": "candidate cut mid-expression (syntax error)",
    }


def _zoo_302(seed: int) -> dict:
    rng = random.Random(seed)
    xs = rng.sample(range(1, 10), 4)
    return {
        "code": "def sum_list(xs):\n    if not xs:\n        return 0\n"
                "    return xs[0]\n",
        "tests": f"assert sum_list({xs}) == {sum(xs)}\n"
                 "assert sum_list([]) == 0\n",
        "triplets": [_FACT_SUM],
        "note": "early return: only the empty edge is handled",
    }


def _zoo_303(seed: int) -> dict:
    return {
        "code": "def max_in_list(xs):\n    if len(xs) < 2:\n"
                "        raise ValueError('degenerate input')\n"
                "    return max(xs)\n",
        "tests": "assert max_in_list([3, 9, 1]) == 9\n"
                 "assert max_in_list([7]) == 7\n",
        "triplets": [{"subject": "max_in_list", "predicate": "computes",
                      "object": "maximum_value"}],
        "note": "rejects the single-element edge the tests demand",
    }


def _zoo_304(seed: int) -> dict:
    return {
        "code": "def count_words(s):\n    return len(s.split())\n",
        "tests": "assert count_words('alpha beta') == 2\n"
                 "assert count_words(None) == 0\n",
        "triplets": [{"subject": "count_words", "predicate": "counts",
                      "object": "whitespace_tokens"}],
        "note": "None input crashes the memorized body",
    }


def _zoo_305(seed: int) -> dict:
    return {
        "code": "def sum_list(xs):\n    return sum(xs) if xs else None\n",
        "tests": "assert sum_list([1, 2, 3]) == 6\n"
                 "assert sum_list([]) == 0\n",
        "triplets": [_FACT_SUM],
        "note": "empty edge returns None instead of 0",
    }


attacks = [
    {"id": "ZOO-301", "category": "truncation",
     "description": "truncated expression, syntax error on execution",
     "generator": "zoo.attacks.truncation:_zoo_301", "seed": 4211,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "sum_list", "generate": _zoo_301},
    {"id": "ZOO-302", "category": "truncation",
     "description": "early return after the empty-case branch",
     "generator": "zoo.attacks.truncation:_zoo_302", "seed": 4212,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "sum_list", "generate": _zoo_302},
    {"id": "ZOO-303", "category": "truncation",
     "description": "raises on the single-element boundary",
     "generator": "zoo.attacks.truncation:_zoo_303", "seed": 4213,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "max_in_list", "generate": _zoo_303},
    {"id": "ZOO-304", "category": "truncation",
     "description": "None input unhandled",
     "generator": "zoo.attacks.truncation:_zoo_304", "seed": 4214,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "count_words", "generate": _zoo_304},
    {"id": "ZOO-305", "category": "truncation",
     "description": "empty edge yields None instead of the unit",
     "generator": "zoo.attacks.truncation:_zoo_305", "seed": 4215,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "sum_list", "generate": _zoo_305},
]
