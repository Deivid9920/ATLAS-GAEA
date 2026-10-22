"""Anchor 3: stats_core against frozen expected values.

Every number below was computed once with the frozen seed and hand
verified (Wilson against reference tables; Holm against the manual
matrix; ECE by hand). These values are the specification."""
import pytest

from gv.stats.stats_core import (wilson_ci, paired_bootstrap, holm,
                                 tost_equivalence, ece, auc_ci,
                                 power_epsilon)

A = [1, 0, 1, 1, 0, 1, 1, 0, 1, 1]
B = [0, 0, 1, 0, 0, 1, 1, 0, 0, 0]


def test_wilson_frozen():
    lo, hi = wilson_ci(7, 10)
    assert abs(lo - 0.39677321997956516) < 1e-12
    assert abs(hi - 0.892210712513788) < 1e-12
    assert wilson_ci(0, 5)[0] == 0.0
    assert wilson_ci(5, 5)[1] == 1.0
    with pytest.raises(ValueError):
        wilson_ci(3, 0)
    with pytest.raises(ValueError):
        wilson_ci(11, 10)


def test_paired_bootstrap_frozen():
    res = paired_bootstrap(A, B, 1000, 42)
    assert res["delta"] == pytest.approx(0.4)
    assert res["ci_lo"] == pytest.approx(0.1)
    assert res["ci_hi"] == pytest.approx(0.7)
    assert res["p_two_sided"] == pytest.approx(0.021)
    again = paired_bootstrap(A, B, 1000, 42)
    assert again == res  # same seed -> bit identical


def test_paired_bootstrap_length_guard():
    with pytest.raises(ValueError):
        paired_bootstrap([1], [1, 2], 100, 42)
    with pytest.raises(ValueError):
        paired_bootstrap([], [], 100, 42)


def test_holm_manual_matrix():
    res = holm([0.01, 0.04, 0.03, 0.005])
    assert res["p_holm"] == pytest.approx([0.03, 0.06, 0.06, 0.02])
    assert res["rejected"] == [True, False, False, True]
    assert holm([]) == {"p_holm": [], "rejected": []}
    one = holm([0.03])
    assert one["rejected"] == [True]


def test_tost_frozen_and_boundary():
    inside = tost_equivalence(A, B, 0.71, 1000, 42)
    assert inside["inside"] is True
    assert inside["ci_lo"] == pytest.approx(0.1)
    assert inside["ci_hi"] == pytest.approx(0.7)
    boundary = tost_equivalence(A, B, 0.70, 1000, 42)
    assert boundary["inside"] is False  # CI endpoint touches epsilon
    same = tost_equivalence(A, A, 0.05, 1000, 42)
    assert same["inside"] is True and same["delta"] == 0.0
    with pytest.raises(ValueError):
        tost_equivalence(A, B, 0.0, 100, 42)


def test_ece_frozen():
    conf = [0.9, 0.8, 0.7, 0.6, 0.4, 0.3, 0.95, 0.85, 0.55, 0.35]
    corr = [1, 1, 0, 1, 0, 0, 1, 1, 0, 1]
    assert ece(conf, corr, 10) == pytest.approx(0.29)
    assert ece([1.0, 0.0], [1, 0], 10) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        ece([0.5], [1, 0], 10)


def test_auc_ci_frozen():
    scores = [0.9, 0.8, 0.7, 0.3, 0.2, 0.6, 0.55, 0.1]
    labels = [1, 1, 1, 0, 0, 0, 1, 0]
    res = auc_ci(scores, labels, 500, 42)
    assert res["auc"] == pytest.approx(0.9375)
    assert 0.0 <= res["ci_lo"] <= res["auc"] <= res["ci_hi"] <= 1.0
    with pytest.raises(ValueError):
        auc_ci([0.5, 0.6], [1, 1], 100, 42)
