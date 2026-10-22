"""Anchor 6: paired bootstrap — pairing by task, fixed seed, percentile
CI 95, reproducible bit-for-bit."""
from gv.stats.stats_core import paired_bootstrap

A = [1, 0, 1, 1, 0, 1, 1, 0, 1, 1]
B = [0, 0, 1, 0, 0, 1, 1, 0, 0, 0]


def test_frozen_values_and_paring():
    res = paired_bootstrap(A, B, 1000, 42)
    assert res == {"delta": 0.4, "ci_lo": 0.1, "ci_hi": 0.7,
                   "p_two_sided": 0.021}


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
