"""stats_core: the single statistical library of the ecosystem.

Pure functions, no I/O, seed passed by parameter. ATLAS and GAEA import
from here; no other unit implements statistics (uniqueness rule of
FASE 1). Ported discipline sources: CASSANDRA (paired bootstrap, Holm,
ECE) re-implemented as new functions with anchor tests, never forked.

Frozen signatures (anchor-tested):
    wilson_ci(k, n, z=1.96) -> (lo, hi)
    paired_bootstrap(a, b, resamples, seed) -> dict
    holm(p_values) -> dict
    tost_equivalence(a, b, epsilon, resamples, seed) -> dict
    ece(confidences, correctness, n_bins=10) -> float
    auc_ci(scores, labels, resamples, seed) -> dict
    power_epsilon(n, variance, power_target, seed, sims) -> float
"""

from __future__ import annotations

import math
import random


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError("k out of range")
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def paired_bootstrap(paired_scores_a, paired_scores_b, resamples: int,
                     seed: int) -> dict:
    """Percentile bootstrap over task-paired differences (a - b).

    Returns {delta, ci_lo, ci_hi, p_two_sided}. Differences are paired
    by task position; both lists must have equal length >= 1.
    """
    if len(paired_scores_a) != len(paired_scores_b):
        raise ValueError("paired lists must have equal length")
    n = len(paired_scores_a)
    if n == 0:
        raise ValueError("empty paired lists")
    diffs = [a - b for a, b in zip(paired_scores_a, paired_scores_b)]
    observed = sum(diffs) / n
    rng = random.Random(seed)
    boots = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        boots.append(total / n)
    boots.sort()

    def pct(q: float) -> float:
        idx = min(int(q * (resamples - 1) + 0.5), resamples - 1)
        return boots[idx]

    # two-sided p: proportion of bootstrap deltas at or beyond |observed|
    # centered on the observed delta (bootstrap null of no effect).
    centered = [b - observed for b in boots]
    extreme = sum(1 for c in centered if abs(c) >= abs(observed))
    return {"delta": observed, "ci_lo": pct(0.025), "ci_hi": pct(0.975),
            "p_two_sided": extreme / resamples}


def holm(p_values) -> dict:
    """Holm step-down adjustment over a closed family.

    Returns {p_holm: [...], rejected: [...]} in the INPUT order, where
    rejected[i] uses alpha = 0.05 (the caller's preregistered alpha).
    """
    m = len(p_values)
    if m == 0:
        return {"p_holm": [], "rejected": []}
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * p_values[idx]
        running = max(running, val)
        adjusted[idx] = min(1.0, running)
    return {"p_holm": adjusted,
            "rejected": [p <= 0.05 for p in adjusted]}


def tost_equivalence(paired_scores_a, paired_scores_b, epsilon: float,
                     resamples: int, seed: int) -> dict:
    """Two one-sided tests via percentile bootstrap of the difference.

    Declares equivalence (inside=True) when the 90% percentile interval
    of the mean difference lies entirely within (-epsilon, +epsilon).
    """
    if epsilon <= 0:
        raise ValueError("epsilon must be positive")
    res = paired_bootstrap(paired_scores_a, paired_scores_b, resamples,
                           seed)
    # 90% CI for TOST (alpha 0.05 two one-sided): percentiles 0.05/0.95
    diffs = [a - b for a, b in zip(paired_scores_a, paired_scores_b)]
    n = len(diffs)
    observed = res["delta"]
    rng = random.Random(seed)
    boots = []
    for _ in range(resamples):
        total = 0.0
        for _ in range(n):
            total += diffs[rng.randrange(n)]
        boots.append(total / n)
    boots.sort()
    lo = boots[min(int(0.05 * (resamples - 1) + 0.5), resamples - 1)]
    hi = boots[min(int(0.95 * (resamples - 1) + 0.5), resamples - 1)]
    inside = (lo > -epsilon) and (hi < epsilon)
    return {"inside": inside, "ci_lo": lo, "ci_hi": hi,
            "delta": observed, "epsilon": epsilon}


def ece(confidences, correctness, n_bins: int = 10) -> float:
    """Expected calibration error over equal-width confidence bins."""
    if len(confidences) != len(correctness):
        raise ValueError("inputs must have equal length")
    if not confidences:
        raise ValueError("empty inputs")
    n = len(confidences)
    total = 0.0
    for b in range(n_bins):
        lo, hi = b / n_bins, (b + 1) / n_bins
        idx = [i for i, c in enumerate(confidences) if lo <= c < hi
               or (b == n_bins - 1 and c == hi)]
        if not idx:
            continue
        conf = sum(confidences[i] for i in idx) / len(idx)
        acc = sum(1 for i in idx if correctness[i]) / len(idx)
        total += (len(idx) / n) * abs(conf - acc)
    return total


def auc_ci(scores, labels, resamples: int, seed: int) -> dict:
    """AUC with percentile bootstrap CI (rank statistic, no scipy).

    labels are 0/1. Returns {auc, ci_lo, ci_hi}. Degenerate all-same-
    label input is an error: a CI over one class is meaningless.
    """
    pos = [s for s, y in zip(scores, labels) if y == 1]
    neg = [s for s, y in zip(scores, labels) if y == 0]
    if not pos or not neg:
        raise ValueError("AUC needs both classes present")
    pairs = [(s, y) for s, y in zip(scores, labels)]

    def auc_of(rows):
        wins = ties = 0
        for sp, _ in [(s, y) for s, y in rows if y == 1]:
            for sn, _ in [(s, y) for s, y in rows if y == 0]:
                if sp > sn:
                    wins += 1
                elif sp == sn:
                    ties += 1
        return (wins + 0.5 * ties) / (len(pos) * len(neg))

    point = auc_of(pairs)
    rng = random.Random(seed)
    boots = []
    n = len(pairs)
    for _ in range(resamples):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        boots.append(auc_of(sample))
    boots.sort()
    lo = boots[min(int(0.025 * (resamples - 1) + 0.5), resamples - 1)]
    hi = boots[min(int(0.975 * (resamples - 1) + 0.5), resamples - 1)]
    return {"auc": point, "ci_lo": lo, "ci_hi": hi}


def power_epsilon(n: int, variance: float, power_target: float,
                  seed: int, sims: int = 4000) -> float:
    """Smallest equivalence margin with TOST power >= target at n.

    The TOST declaration event at true delta 0 is: the 90% interval of
    the mean (mean +/- z90*se) lies entirely inside (-eps, +eps), i.e.
    |mean| + hw < eps with hw = z90*se. Monte Carlo over seeded
    simulated experiments draws n differences from N(0, variance) per
    sim; the grid search returns the smallest epsilon on a 0.01 grid
    whose simulated power reaches the target.
    """
    if n <= 1:
        raise ValueError("n must exceed 1")
    if variance <= 0:
        raise ValueError("variance must be positive")
    if not 0 < power_target < 1:
        raise ValueError("power_target must be in (0, 1)")
    sd = math.sqrt(variance)
    se = sd / math.sqrt(n)
    z90 = 1.6448536269514722  # two-sided 90% normal critical value
    hw = z90 * se
    # One seeded stream of simulated experiments: each sim draws n
    # differences from N(0, variance) and records the standardized mean
    # (mean / se). Power at epsilon = P(|mean| + hw < epsilon).
    rng = random.Random(seed)
    z_means = []
    for _ in range(sims):
        mean = sum(rng.gauss(0.0, sd) for _ in range(n)) / n
        z_means.append(mean / se)

    def power(eps: float) -> float:
        limit = (eps - hw) / se
        if limit <= 0:
            return 0.0
        return sum(1 for z in z_means if abs(z) < limit) / sims

    grid = [0.01 * i for i in range(1, 101)]
    for eps in grid:
        if power(eps) >= power_target:
            return round(eps, 4)
    return 1.0
