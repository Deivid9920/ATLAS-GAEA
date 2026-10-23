"""Calibration metrics: ECE, Brier and reliability diagrams.

ECE uses 10 equal-width bins over [0, 1]; the Brier score is the mean
squared difference between score and outcome. Probes are trained for
ranking (AUC), not for probability reporting - these metrics quantify
how far their scores sit from usable probabilities, which is why the
abstention thresholds in the generation phase are rank-based.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def ece(y_true: np.ndarray, scores: np.ndarray, n_bins: int = 10) -> float:
    """Expected calibration error over equal-width bins."""
    y = np.asarray(y_true).astype(float)
    s = np.asarray(scores, dtype=float)
    if len(y) != len(s):
        raise ValueError("y_true and scores must have the same length")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # scores exactly at 1.0 fall into the last bin
    bin_idx = np.clip(np.digitize(s, edges[1:-1], right=False), 0,
                      n_bins - 1)
    total = len(y)
    e = 0.0
    for b in range(n_bins):
        mask = bin_idx == b
        if not mask.any():
            continue
        conf = s[mask].mean()
        acc = y[mask].mean()
        e += (mask.sum() / total) * abs(acc - conf)
    return float(e)


def brier(y_true: np.ndarray, scores: np.ndarray) -> float:
    y = np.asarray(y_true).astype(float)
    s = np.asarray(scores, dtype=float)
    return float(np.mean((s - y) ** 2))


def reliability_diagram(y_true, scores, ax: plt.Axes | None = None,
                        n_bins: int = 10):
    """Draw the reliability diagram; return (fig, info).

    info carries ece, brier and the per-bin table. When ax is provided
    the diagram is drawn there (notebook grid layouts); otherwise a
    standalone figure is created.
    """
    y = np.asarray(y_true).astype(int)
    s = np.asarray(scores, dtype=float)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_idx = np.clip(np.digitize(s, edges[1:-1], right=False), 0,
                      n_bins - 1)
    rows = []
    for b in range(n_bins):
        mask = bin_idx == b
        rows.append({
            "bin": b,
            "count": int(mask.sum()),
            "mean_score": float(s[mask].mean()) if mask.any() else np.nan,
            "fraction_true": float(y[mask].mean()) if mask.any() else np.nan,
        })
    bins = pd.DataFrame(rows)
    info = {"ece": ece(y, s, n_bins), "brier": brier(y, s),
            "bins": bins}

    if ax is None:
        fig, ax = plt.subplots(figsize=(4.8, 4.4))
    else:
        fig = ax.figure

    centers = 0.5 * (edges[:-1] + edges[1:])
    width = edges[1] - edges[0]
    plotted = bins[bins["count"] > 0]
    ax.bar(plotted["bin"] * width + width / 2, plotted["fraction_true"],
           width=width * 0.92, color="#4c78a8", alpha=0.85,
           label="observed")
    ax.plot([0, 1], [0, 1], ls="--", c="grey", lw=1, label="perfect")
    ax.set_xlabel("probe score (mean per bin)")
    ax.set_ylabel("fraction true")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left", fontsize=8)
    return fig, info
