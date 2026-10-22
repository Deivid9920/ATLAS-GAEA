"""Anchor 4: Holm step-down against the hand-computed matrix.

Manual matrix for p = [0.01, 0.04, 0.03, 0.005], m = 4:
  rank 0: 0.005 * 4 = 0.02   (cummax 0.02)
  rank 1: 0.010 * 3 = 0.03   (cummax 0.03)
  rank 2: 0.030 * 2 = 0.06   (cummax 0.06)
  rank 3: 0.040 * 1 = 0.04   (cummax 0.06)
Input-order adjustments: [0.03, 0.06, 0.06, 0.02].
"""
from gv.stats.stats_core import holm


def test_holm_against_manual_matrix():
    res = holm([0.01, 0.04, 0.03, 0.005])
    assert [round(p, 10) for p in res["p_holm"]] == \
        [0.03, 0.06, 0.06, 0.02]
    assert res["rejected"] == [True, False, False, True]


def test_holm_monotone_and_bounded():
    res = holm([0.9, 0.8, 0.7, 0.6, 0.5])
    assert all(p <= 1.0 for p in res["p_holm"])
    assert res["rejected"] == [False] * 5


def test_holm_input_order_preserved():
    res = holm([0.2, 0.004])
    assert res["p_holm"][1] <= res["p_holm"][0]
    assert res["rejected"] == [False, True]
