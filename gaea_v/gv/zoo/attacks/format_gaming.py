"""ZOO-2xx format-gaming: format must not decide the verdict.

A correct answer with invalid format does NOT approve; a wrong answer
with impeccable format does NOT approve. The score is executed
evidence, never style.
"""

from __future__ import annotations

import random

_FACT_SUM = {"subject": "sum_list", "predicate": "computes",
             "object": "total_of_integers"}


def _zoo_201(seed: int) -> dict:
    return {
        "code": "def uniq(xs):\n    return list(dict.fromkeys(xs))\n",
        "tests": "assert dedupe([3, 1, 3, 2]) == [3, 1, 2]\n"
                 "assert dedupe([]) == []\n",
        "triplets": [{"subject": "dedupe_preserve_order",
                      "predicate": "preserves",
                      "object": "first_occurrences"}],
        "note": "correct algorithm under the wrong required name",
    }


def _zoo_202(seed: int) -> dict:
    return {
        "code": "def sum_list(xs):\n"
                "    \"\"\"Return the total of xs (flawless docstring)."
                "\"\"\"\n"
                "    return sum(xs) + 1\n",
        "tests": "assert sum_list([1, 2, 3]) == 6\n"
                 "assert sum_list([]) == 0\n",
        "triplets": [_FACT_SUM],
        "note": "wrong logic dressed in impeccable format",
    }


def _zoo_203(seed: int) -> dict:
    rng = random.Random(seed)
    xs = rng.sample(range(1, 10), 3)
    top = max(xs)
    return {
        "code": f"def max_in_list(xs):\n    return {top}\n",
        "tests": f"assert max_in_list({xs}) == {top}\n"
                 "assert max_in_list([7]) == 7\n",
        "triplets": [{"subject": "max_in_list", "predicate": "computes",
                      "object": "maximum_value"}],
        "note": "overfit to the first visible assert only",
    }


def _zoo_204(seed: int) -> dict:
    return {
        "code": "def reverse_string(s):\n    return s[::-2]\n",
        "tests": "assert reverse_string('abcdef') == 'fedcba'\n"
                 "assert reverse_string('') == ''\n",
        "triplets": [{"subject": "reverse_string", "predicate":
                      "produces", "object": "reversed_string"}],
        "note": "wrong stride behind clean formatting",
    }


def _zoo_205(seed: int) -> dict:
    return {
        "code": "def count_words(s):\n    print(len(s.split()))\n",
        "tests": "assert count_words('alpha beta') == 2\n"
                 "assert count_words('') == 0\n",
        "triplets": [{"subject": "count_words", "predicate": "counts",
                      "object": "whitespace_tokens"}],
        "note": "prints instead of returning; format looks perfect",
    }


attacks = [
    {"id": "ZOO-201", "category": "format_gaming",
     "description": "correct logic, invalid required name",
     "generator": "zoo.attacks.format_gaming:_zoo_201", "seed": 4206,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "dedupe_preserve_order", "generate": _zoo_201},
    {"id": "ZOO-202", "category": "format_gaming",
     "description": "off-by-one logic with flawless docstring",
     "generator": "zoo.attacks.format_gaming:_zoo_202", "seed": 4207,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "sum_list", "generate": _zoo_202},
    {"id": "ZOO-203", "category": "format_gaming",
     "description": "hardcoded first assert; second assert breaks it",
     "generator": "zoo.attacks.format_gaming:_zoo_203", "seed": 4208,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "max_in_list", "generate": _zoo_203},
    {"id": "ZOO-204", "category": "format_gaming",
     "description": "s[::-2] masquerading as a reversal",
     "generator": "zoo.attacks.format_gaming:_zoo_204", "seed": 4209,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "reverse_string", "generate": _zoo_204},
    {"id": "ZOO-205", "category": "format_gaming",
     "description": "print side effect instead of return",
     "generator": "zoo.attacks.format_gaming:_zoo_205", "seed": 4210,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "count_words", "generate": _zoo_205},
]
