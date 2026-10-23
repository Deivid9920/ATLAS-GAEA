"""Statistical anchor of CASSANDRA: the numerical specification.

Every metric reported anywhere in the project (probes, notebooks, README)
is computed here. Never reimplement a metric in a notebook or module;
import from cassandra_ns.probes.stats. tests/test_stats.py pins every
number by hand-derived fixtures, so this file is treated as immutable.
"""

from __future__ import annotations

import numpy as np


def roc_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Area under the ROC curve via the Mann-Whitney rank statistic.

    Ties get 0.5 credit. Raises ValueError when y_true contains a single
    class, because the AUC is undefined there.
    """
    y = np.asarray(y_true).astype(int)
    s = np.asarray(scores, dtype=np.float64)
    if len(y) != len(s):
        raise ValueError("y_true and scores must have the same length")
    positives = (y == 1).sum()
    negatives = (y == 0).sum()
    if positives == 0 or negatives == 0:
        raise ValueError("roc_auc requires both classes in y_true")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=np.float64)
    sorted_scores = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        # average rank (1-based) of the tied block i..j
        ranks[order[i : j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    sum_pos = ranks[y == 1].sum()
    # Mann-Whitney U for the positive group: R_pos - n_pos(n_pos+1)/2.
    # Correction note (documented, Fase 3 audit): this anchor shipped
    # with n_pos(n_pos-1)/2, which inflates the AUC by exactly
    # 1/n_neg on tied scores (verified against sklearn and
    # scipy.stats.rankdata); the honest constant is the (n_pos+1)
    # triangle number.
    u = sum_pos - positives * (positives + 1) / 2.0
    return float(u / (positives * negatives))


def bootstrap_ci(y_true: np.ndarray, scores: np.ndarray,
                 metric_fn, n_boot: int, ci: float, seed: int
                 ) -> tuple[float, float, float]:
    """Percentile bootstrap CI for metric_fn(y_true, scores).

    Returns (point, lo, hi) with lo/hi the (1-ci)/2 and 1-(1-ci)/2
    quantiles of the bootstrap distribution. Deterministic under seed.
    """
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true)
    scores = np.asarray(scores)
    point = float(metric_fn(y_true, scores))
    n = len(y_true)
    stats = np.empty(n_boot, dtype=np.float64)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        stats[b] = metric_fn(y_true[idx], scores[idx])
    alpha = (1.0 - ci) / 2.0
    lo, hi = np.quantile(stats, [alpha, 1.0 - alpha])
    return point, float(lo), float(hi)


def paired_bootstrap_diff_auc(y_true: np.ndarray, scores_a: np.ndarray,
                              scores_b: np.ndarray, n_boot: int, ci: float,
                              seed: int) -> dict:
    """Paired bootstrap for AUC(a) - AUC(b): same resampled indices for
    both systems, so the correlation between systems is preserved.

    Resamples that contain a single class have an undefined AUC; they
    are REDRAWN (not interpolated) and the number of such draws is
    reported as ``n_resamples_skipped``. On non-degenerate data the
    count is 0 and the distribution is identical to the previous
    unconditional scheme.

    Returns {diff, lo, hi, p_two_sided, n_resamples_skipped}.
    p = 2 * min(P(diff>=0), P(diff<=0)) over the bootstrap distribution,
    capped at 1.0.
    """
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true).astype(int)
    scores_a = np.asarray(scores_a, dtype=np.float64)
    scores_b = np.asarray(scores_b, dtype=np.float64)
    assert len(y_true) == len(scores_a) == len(scores_b)
    diff_point = roc_auc(y_true, scores_a) - roc_auc(y_true, scores_b)
    n = len(y_true)
    diffs = np.empty(n_boot, dtype=np.float64)
    skipped = 0
    max_draws = 100 * n_boot
    draws = 0
    b = 0
    while b < n_boot:
        if draws >= max_draws:
            raise ValueError(
                f"bootstrap degenerate: {skipped} single-class resamples "
                f"after {draws} draws; subset too small or too "
                "class-imbalanced for a paired AUC bootstrap")
        idx = rng.integers(0, n, size=n)
        draws += 1
        yb = y_true[idx]
        if yb.min() == yb.max():
            skipped += 1
            continue
        diffs[b] = roc_auc(yb, scores_a[idx]) - roc_auc(yb, scores_b[idx])
        b += 1
    alpha = (1.0 - ci) / 2.0
    lo, hi = np.quantile(diffs, [alpha, 1.0 - alpha])
    p = 2.0 * min((diffs >= 0).mean(), (diffs <= 0).mean())
    return {"diff": float(diff_point), "lo": float(lo), "hi": float(hi),
            "p_two_sided": float(min(p, 1.0)),
            "n_resamples_skipped": int(skipped)}


def holm_bonferroni(pvals: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, returned in the ORIGINAL order.

    Sorted p_(i) gets adj_i = max_{j<=i}( (m - j) * p_(j) ), capped at 1,
    enforced monotone non-decreasing.
    """
    m = len(pvals)
    if m == 0:
        return []
    order = np.argsort(np.asarray(pvals, dtype=np.float64))
    sorted_p = np.asarray(pvals, dtype=np.float64)[order]
    adjusted_sorted = np.empty(m, dtype=np.float64)
    running_max = 0.0
    for i in range(m):
        candidate = (m - i) * sorted_p[i]
        running_max = max(running_max, candidate)
        adjusted_sorted[i] = min(running_max, 1.0)
    adjusted = np.empty(m, dtype=np.float64)
    adjusted[order] = adjusted_sorted
    return [float(a) for a in adjusted]
