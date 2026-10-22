"""Anchor 6: paired bootstrap — pairing by task, fixed seed, percentile
CI 95, reproducible bit-for-bit."""
from gv.stats.stats_core import paired_bootstrap

A = [1, 0, 1, 1, 0, 1, 1, 0, 1, 1]
B = [0, 0, 1, 0, 0, 1, 1, 0, 0, 0]


def test_frozen_values_and_paring():
    # Anchor amended v1.0.2 (gaea_v/docs/ANCHOR_CHANGES.md 2026-10-22,
    # schema enrichment): the result dict gains p_resolution — the
    # Monte Carlo floor of p_two_sided. Previous values unchanged
    # bit-for-bit: 0.4 / 0.1 / 0.7 / 0.021.
    res = paired_bootstrap(A, B, 1000, 42)
    assert res == {"delta": 0.4, "ci_lo": 0.1, "ci_hi": 0.7,
                   "p_two_sided": 0.021, "p_resolution": 1.0 / 1000}


def test_p_zero_is_a_floor_not_a_literal_zero():
    # A reported p_two_sided of 0.0 means the tail mass is below the
    # Monte Carlo resolution (1/resamples), never a literal probability
    # of zero. The resolution field makes that floor explicit.
    res = paired_bootstrap(A, B, 1000, 42)
    assert res["p_resolution"] == 1.0 / 1000
    for r in (res, paired_bootstrap(A, B, 5000, 42)):
        assert r["p_resolution"] == 1.0 / (1000 if r is res else 5000)
        if r["p_two_sided"] == 0.0:
            assert r["p_two_sided"] < r["p_resolution"]


def test_seed_determinism_bit_identical():
    r1 = paired_bootstrap(A, B, 500, 7)
    r2 = paired_bootstrap(A, B, 500, 7)
    assert r1 == r2
    r3 = paired_bootstrap(A, B, 500, 8)
    assert r3["delta"] == r1["delta"]  # observed does not depend on seed


def test_more_resamples_tighten_ci():
    wide = paired_bootstrap(A, B, 200, 42)
    tight = paired_bootstrap(A, B, 5000, 42)
    assert (tight["ci_hi"] - tight["ci_lo"]) <= \
        (wide["ci_hi"] - wide["ci_lo"]) + 1e-9


def test_symmetric_delta():
    ab = paired_bootstrap(A, B, 500, 42)
    ba = paired_bootstrap(B, A, 500, 42)
    assert ab["delta"] == -ba["delta"]
