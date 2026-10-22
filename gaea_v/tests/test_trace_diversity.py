"""Tests del contrato de diversidad de trazas (FASE 5.e).

Determinismo por semilla, sensibilidad al colapso de modo y la regla
de promocion heredada de NS (caida > 20% bloquea).
"""

from __future__ import annotations

from gv.lin.trace_diversity import (estimated_jaccard, minhash_signature,
                                    trace_diversity)

SAME = ["def sum_list(xs):\n    return sum(xs)\n"] * 8
DISTINCT = [
    "def sum_list(xs):\n    return sum(xs)\n",
    "def reverse_string(s):\n    return s[::-1]\n",
    "def is_palindrome(s):\n    return s == s[::-1]\n",
    "def max_in_list(xs):\n    best = xs[0]\n    for x in xs:\n"
    "        if x > best:\n            best = x\n    return best\n",
    "def count_words(s):\n    return len(s.split())\n",
    "def dedupe(xs):\n    out = []\n    for x in xs:\n"
    "        if x not in out:\n            out.append(x)\n"
    "    return out\n",
    "def clamp(v, lo, hi):\n    return max(lo, min(v, hi))\n",
    "def digit_sum(n):\n    return sum(int(c) for c in str(n))\n",
]


def test_identical_traces_single_mode():
    d = trace_diversity(SAME)
    assert d["n_clusters"] == 1
    assert d["cluster_entropy"] == 0.0
    assert d["largest_cluster_frac"] == 1.0
    assert d["pairwise_diversity"] == 0.0


def test_distinct_traces_spread():
    d = trace_diversity(DISTINCT)
    assert d["n_clusters"] >= 6
    assert d["cluster_entropy"] > 0.8
    assert d["pairwise_diversity"] > 0.5


def test_deterministic_seeded():
    a = trace_diversity(DISTINCT)
    b = trace_diversity(list(reversed(DISTINCT)))
    assert a["n_clusters"] == b["n_clusters"]
    assert a["pairwise_diversity"] == b["pairwise_diversity"]


def test_empty_traces_honest_zero():
    d = trace_diversity([])
    assert d == {"n_traces": 0, "n_clusters": 0,
                 "cluster_entropy": 0.0, "pairwise_diversity": 0.0,
                 "largest_cluster_frac": 0.0}


def test_ns_promotion_rule():
    """La runda no promueve si la diversidad cae > 20% vs baseline."""
    baseline = trace_diversity(DISTINCT)
    round_ = trace_diversity(SAME)
    drop = 1.0 - (round_["cluster_entropy"]
                  / max(baseline["cluster_entropy"], 1e-12))
    assert drop > 0.20  # collapse blocks promotion


def test_signature_stability_on_prefix():
    s1 = minhash_signature("alpha beta gamma delta epsilon zeta")
    s2 = minhash_signature("alpha beta gamma delta epsilon zeta")
    assert s1 == s2
    assert estimated_jaccard(s1, s2) == 1.0
