"""Regression pins for the tie-handling of the roc_auc anchor.

The anchor's Mann-Whitney constant shipped with an off-by-one
(n_pos(n_pos-1)/2 instead of n_pos(n_pos+1)/2) that inflated the AUC
by exactly 1/n_neg on tied scores. These tests pin the corrected
behavior against scikit-learn on tie-heavy and continuous scores, so
the correction cannot silently regress.
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import roc_auc_score

from cassandra_ns.probes.stats import roc_auc

_TIE_CASES = [
    (np.array([1, 0, 1, 0, 1, 0, 1, 0]),
     np.array([1.0, 1.0, 1.0, 0.5, 0.5, 0.0, 0.0, 0.0])),
    (np.array([0, 1, 1, 0, 0, 1, 0, 1]),
     np.array([0.5, 0.5, 1.0, 0.0, 0.5, 1.0, 0.5, 1.0])),
    (np.array([1, 1, 1, 0, 0, 0]),
     np.array([0.9, 0.9, 0.9, 0.1, 0.1, 0.1])),
]


@pytest.mark.parametrize("y,s", _TIE_CASES)
def test_roc_auc_matches_sklearn_on_ties(y, s) -> None:
    assert roc_auc(y, s) == pytest.approx(roc_auc_score(y, s))


def test_roc_auc_perfect_separation_with_ties_is_one() -> None:
    y = np.array([1] * 99 + [0] * 101)
    s = np.where(y == 1, 1.0, 0.0)
    assert roc_auc(y, s) == pytest.approx(1.0)


def test_roc_auc_continuous_scores_match_sklearn() -> None:
    rng = np.random.default_rng(42)
    y = rng.integers(0, 2, 400)
    s = np.where(y == 1, 0.65, 0.35) + rng.normal(0, 0.18, 400)
    assert roc_auc(y, s) == pytest.approx(roc_auc_score(y, s),
                                          abs=1e-12)
