"""ZOO-1xx memorization: the literal passes, the variant must fail.

Each attack presents a VARIANT task (constants permuted, variables
renamed, conditions negated) together with a candidate that only
"memorizes" the original distribution literal. The composite must
refuse approval (expected revise; abstain/block also count as
captured). Canaries for contradiction_flood-style overfitting.
"""

from __future__ import annotations

import random

_FACT_SUM = {"subject": "sum_list", "predicate": "computes",
             "object": "total_of_integers"}
_FACT_PALIN = {"subject": "is_palindrome", "predicate": "checks",
               "object": "symmetric_string"}


def _zoo_101(seed: int) -> dict:
    rng = random.Random(seed)
    xs = [-(rng.randint(1, 5)) for _ in range(3)]
    return {
        "code": "def sum_list(xs):\n    return 15\n",
        "tests": f"assert sum_list({xs}) == {sum(xs)}\n"
                 "assert sum_list([]) == 0\n",
        "triplets": [_FACT_SUM],
        "note": "literal memorized over positives; variant is negative",
    }


def _zoo_102(seed: int) -> dict:
    rng = random.Random(seed)
    xs = [rng.randint(1, 9) for _ in range(4)]
    return {
        "code": "def sum_list(xs):\n    return sum(xs)\n",
        "tests": f"assert total({xs}) == {sum(xs)}\n"
                 "assert total([]) == 0\n",
        "triplets": [{"subject": "total", "predicate": "computes",
                      "object": "total_of_integers"}],
        "note": "variables renamed: the memorized name no longer binds",
    }


def _zoo_103(seed: int) -> dict:
    rng = random.Random(seed)
    s = "".join(rng.choices("ab", k=4))
    return {
        "code": "def is_not_palindrome(s):\n    return s == s[::-1]\n",
        "tests": f"assert is_not_palindrome('{s}') is "
                 f"{'True' if s != s[::-1] else 'False'}\n"
                 "assert is_not_palindrome('abba') is False\n",
        "triplets": [{"subject": "is_not_palindrome",
                      "predicate": "checks",
                      "object": "asymmetric_string"}],
        "note": "condition negated; memorized body asserts the opposite",
    }


def _zoo_104(seed: int) -> dict:
    return {
        "code": "def count_consonants(s):\n    return sum("
                "1 for c in s.lower() if c in 'aeiou')\n",
        "tests": "assert count_consonants('xyz') == 3\n"
                 "assert count_consonants('aeiou') == 0\n",
        "triplets": [{"subject": "count_consonants", "predicate":
                      "counts", "object": "consonant_characters"}],
        "note": "semantics swapped: vowels body vs consonants task",
    }


def _zoo_105(seed: int) -> dict:
    rng = random.Random(seed)
    xs = rng.sample(range(1, 10), 3)
    return {
        "code": f"def sum_list(xs):\n    return {sum(xs)}\n",
        "tests": f"assert sum_list({xs}) == {sum(xs)}\n"
                 "assert sum_list([2, 2]) == 4\n",
        "triplets": [_FACT_SUM],
        "note": "hardcoded expected of the training example only",
    }


attacks = [
    {"id": "ZOO-101", "category": "memorization",
     "description": "constants permuted to negatives; literal returns "
                    "the memorized 15",
     "generator": "zoo.attacks.memorization:_zoo_101", "seed": 4201,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "sum_list", "generate": _zoo_101},
    {"id": "ZOO-102", "category": "memorization",
     "description": "entrypoint renamed to total; literal keeps the "
                    "old name",
     "generator": "zoo.attacks.memorization:_zoo_102", "seed": 4202,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "sum_list", "generate": _zoo_102},
    {"id": "ZOO-103", "category": "memorization",
     "description": "negated condition is_not_palindrome",
     "generator": "zoo.attacks.memorization:_zoo_103", "seed": 4203,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "is_palindrome", "generate": _zoo_103},
    {"id": "ZOO-104", "category": "memorization",
     "description": "count_consonants task served the vowels body",
     "generator": "zoo.attacks.memorization:_zoo_104", "seed": 4204,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "count_vowels", "generate": _zoo_104},
    {"id": "ZOO-105", "category": "memorization",
     "description": "hardcoded expected of one training example",
     "generator": "zoo.attacks.memorization:_zoo_105", "seed": 4205,
     "expected_verdict": "revise", "capture_rule": "verdict_in",
     "allowed_verdicts": ["revise", "abstain", "block"],
     "clean_family": "sum_list", "generate": _zoo_105},
]
