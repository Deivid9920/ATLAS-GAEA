"""Anchor 5: TOST declares equivalence inside epsilon only, with exact
boundary cases."""
import pytest

from gv.stats.stats_core import tost_equivalence

A = [1, 0, 1, 1, 0, 1, 1, 0, 1, 1]
B = [0, 0, 1, 0, 0, 1, 1, 0, 0, 0]


def test_inside_declares_equivalence():
    res = tost_equivalence(A, B, 0.71, 1000, 42)
    assert res["inside"] is True
    assert res["ci_lo"] > -0.71 and res["ci_hi"] < 0.71


def test_outside_refuses():
    res = tost_equivalence(A, B, 0.38, 1000, 42)
    assert res["inside"] is False


def test_exact_boundary_is_not_inside():
    # 90% CI ends exactly at 0.7: epsilon == endpoint -> NOT inside
    res = tost_equivalence(A, B, 0.70, 1000, 42)
    assert res["inside"] is False


def test_identical_pairs_equivalent_at_any_positive_epsilon():
    res = tost_equivalence(A, A, 0.01, 1000, 42)
    assert res["inside"] is True and res["delta"] == 0.0


def test_epsilon_must_be_positive():
    with pytest.raises(ValueError):
        tost_equivalence(A, B, -0.1, 1000, 42)
