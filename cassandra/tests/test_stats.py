"""Statistical anchor tests: bootstrap, paired comparison, Holm.

Fixtures are hand-derived: the synthetic AUC is deterministic under
seed 42 and every expected value is pinned by construction, so any
reimplementation of a metric that drifts breaks these tests first.
"""

from __future__ import annotations

import numpy as np
import pytest

from cassandra_ns.probes.stats import (bootstrap_ci, holm_bonferroni,
                                        paired_bootstrap_diff_auc, roc_auc)

_RNG = np.random.default_rng(42)
Y = np.array([0, 1] * 200, dtype=int)
_RNG.shuffle(Y)
SCORES = np.where(Y == 1, 0.65, 0.35) + _RNG.normal(0.0, 0.18, size=Y.size)


def test_bootstrap_ci_contains_point_and_is_deterministic() -> None:
    point, lo, hi = bootstrap_ci(Y, SCORES, roc_auc, n_boot=500, ci=0.95,
                                 seed=42)
    assert lo <= point <= hi
    point2, lo2, hi2 = bootstrap_ci(Y, SCORES, roc_auc, n_boot=500, ci=0.95,
                                    seed=42)
    assert (point, lo, hi) == (point2, lo2, hi2)


def test_paired_bootstrap_contract() -> None:
    baseline = SCORES * 0.9  # slightly worse ordering-preserving system
    result = paired_bootstrap_diff_auc(Y, SCORES, baseline, n_boot=300,
                                       ci=0.95, seed=42)
    point = roc_auc(Y, SCORES) - roc_auc(Y, baseline)
    assert result["diff"] == pytest.approx(point)
    assert result["lo"] <= result["diff"] <= result["hi"]
    assert 0.0 <= result["p_two_sided"] <= 1.0


def test_paired_bootstrap_is_deterministic() -> None:
    a = paired_bootstrap_diff_auc(Y, SCORES, SCORES * 0.9, 200, 0.95, seed=7)
    b = paired_bootstrap_diff_auc(Y, SCORES, SCORES * 0.9, 200, 0.95, seed=7)
    assert a == b


def test_holm_hand_value() -> None:
    # sorted: .005 .01 .03 .04 -> adj .02 .03 .06 .06 -> original order
    assert holm_bonferroni([0.01, 0.04, 0.03, 0.005]) \
        == pytest.approx([0.03, 0.06, 0.06, 0.02])


def test_holm_caps_at_one_and_preserves_order() -> None:
    adjusted = holm_bonferroni([0.4, 0.9])
    assert adjusted == pytest.approx([0.8, 0.9])
    p = [0.2, 0.05, 0.5]
    adjusted = holm_bonferroni(p)
    assert adjusted[1] <= adjusted[0] <= adjusted[2]


def test_requires_both_classes() -> None:
    with pytest.raises(ValueError):
        roc_auc(np.array([1, 1]), np.array([0.5, 0.6]))
