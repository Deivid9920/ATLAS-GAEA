"""Anchor 7: power_epsilon validated against simulation and closed
form. The TOST event at delta 0 is |mean| + hw < eps with
hw = z90*se; the closed form for power 0.80 is
eps = z80*se + z90*se with z80 = 1.2815515655446004."""
from gv.stats.stats_core import power_epsilon


def test_frozen_values_seed_42():
    assert power_epsilon(100, 0.25, 0.80, 42, 4000) == 0.15
    assert power_epsilon(100, 0.09, 0.80, 42, 4000) == 0.09


def test_closed_form_agreement():
    import math
    z90 = 1.6448536269514722
    z80 = 1.2815515655446004
    se = math.sqrt(0.25 / 100)
    closed = z80 * se + z90 * se
    sim = power_epsilon(100, 0.25, 0.80, 42, 4000)
    assert abs(sim - closed) <= 0.02  # 0.01 grid + MC noise


def test_more_variance_needs_larger_epsilon():
    small = power_epsilon(100, 0.05, 0.80, 42, 4000)
    large = power_epsilon(100, 0.50, 0.80, 42, 4000)
    assert large > small


def test_more_power_needs_larger_epsilon():
    p80 = power_epsilon(100, 0.25, 0.80, 42, 2000)
    p95 = power_epsilon(100, 0.25, 0.95, 42, 2000)
    assert p95 > p80


def test_higher_n_shrinks_epsilon():
    n50 = power_epsilon(50, 0.25, 0.80, 42, 2000)
    n400 = power_epsilon(400, 0.25, 0.80, 42, 2000)
    assert n400 < n50


def test_guards():
    import pytest
    with pytest.raises(ValueError):
        power_epsilon(1, 0.25, 0.80, 42)
    with pytest.raises(ValueError):
        power_epsilon(100, 0.0, 0.80, 42)
    with pytest.raises(ValueError):
        power_epsilon(100, 0.25, 1.5, 42)
