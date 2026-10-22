"""Anchor 12: probe activation contract — AUC IC95 excludes 0.5
activates (w=0.20, ECE reported); no signal deactivates with cause;
the neutral 0.5 is forbidden. ECE above the cap forces tau
recalibration before activation."""
import pytest

from gv.probe.calibration import (probe_decision, renormalize,
                                  ProbeContractError)


def _data(delta: float, n: int = 200, seed: int = 42):
    import random
    rng = random.Random(seed)
    scores, labels, confidences, correctness = [], [], [], []
    for i in range(n):
        y = rng.randint(0, 1)
        score = min(1.0, max(0.0, 0.5 + delta * (1 if y else -1)
                             + rng.gauss(0, 0.05)))
        conf = min(1.0, max(0.0, score))
        scores.append(score)
        labels.append(y)
        confidences.append(conf)
        correctness.append(1 if (score >= 0.5) == bool(y) else 0)
    return scores, labels, confidences, correctness


def test_strong_signal_activates():
    scores, labels, conf, corr = _data(0.35)
    d = probe_decision(scores, labels, corr, corr, seed=42)
    assert d["status"] == "active"
    assert d["weight"] == 0.20
    assert d["cause"] == "auc_ci_excludes_050"
    assert d["ece"] is not None and d["auc"] is not None


def test_no_signal_deactivates_with_cause():
    scores, labels, conf, corr = _data(0.0)
    d = probe_decision(scores, labels, conf, corr, seed=42)
    assert d["status"] == "desactivado"
    assert d["cause"] == "probe_desactivado"
    assert d["weight"] == 0.0


def test_high_ece_blocks_activation_for_recalibration():
    scores, labels, conf, corr = _data(0.35)
    d = probe_decision(scores, labels, conf, corr, ece_max=0.0,
                       seed=42)
    assert d["status"] == "desactivado"
    assert d["recalibrate_tau"] is True
    assert d["cause"] == "probe_desactivado_ece_alto"


def test_neutral_is_never_an_outcome():
    scores, labels, conf, corr = _data(0.0)
    d = probe_decision(scores, labels, conf, corr, seed=42)
    assert d["status"] in ("active", "desactivado")


def test_renormalization_matches_s06_math():
    r = renormalize({"programmatic": 0.45, "symbolic": 0.35,
                     "probe": 0.20}, "probe")
    assert r["programmatic"] == pytest.approx(0.5625)
    assert r["symbolic"] == pytest.approx(0.4375)
    assert sum(r.values()) == pytest.approx(1.0)
    with pytest.raises(ProbeContractError):
        renormalize({"programmatic": 0.45}, "probe")


def test_labels_need_both_classes():
    with pytest.raises(ProbeContractError):
        probe_decision([0.9, 0.8], [1, 1], [0.9, 0.8], [1, 0])
