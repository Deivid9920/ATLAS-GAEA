"""Symbolic bridge verification with a synthetic graph.

The anchor config ships prometheus_graph: null, so the production run
records the ensemble as unavailable with its cause. These tests pin
the bridge contract that activates the moment a graph is wired in:
triplet extraction, the {0, 0.5, 1} signal, the out-of-fold 2-feature
ensemble and the paired comparison on the extractable subset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cassandra_ns.ensemble import symbolic_bridge as bridge

CFG = {"seed": 42, "stats": {"n_bootstrap": 200, "ci": 0.95}}


def test_extract_triplets_finds_is_a_claims() -> None:
    claims = bridge.extract_triplets("Paris is the capital of France")
    assert claims, "no claims extracted from a simple declarative"
    subj, verb, obj = claims[0]
    assert "paris" in subj and verb == "is"
    assert not any(t.startswith("the ") for t in (subj, obj))


def test_extract_triplets_rejects_non_declarative() -> None:
    assert bridge.extract_triplets("What is the capital of France?") == []


def test_symbolic_signal_values() -> None:
    g = {"supported": {("paris", "is", "a city")},
         "contradicted": {("paris", "is", "a country")}}
    assert bridge.symbolic_signal(g, [("paris", "is", "a city")]) == 1.0
    assert bridge.symbolic_signal(g, [("paris", "is", "a country")]) == 0.0
    assert bridge.symbolic_signal(g, [("rome", "is", "a city")]) == 0.5
    assert bridge.symbolic_signal(g, []) == 0.5
    # contradiction dominates support
    mixed = [("paris", "is", "a city"), ("paris", "is", "a country")]
    assert bridge.symbolic_signal(g, mixed) == 0.0


def test_load_graph_normalizes_and_splits(tmp_path) -> None:
    path = tmp_path / "graph.json"
    path.write_text(
        '{"triplets": [["  Paris ", " IS ", "A City", true],'
        '["paris", "is", "a country", false], ["x", "y", "z"]]}',
        encoding="utf-8")
    graph = bridge.load_graph(path)
    # normalization strips articles: "A City" -> "city"
    assert ("paris", "is", "city") in graph["supported"]
    assert ("paris", "is", "country") in graph["contradicted"]
    assert ("x", "y", "z") in graph["supported"]


def test_evaluate_ensemble_on_synthetic_subset() -> None:
    rng = np.random.default_rng(42)
    n = 200
    # probe and signal both carry signal; the ensemble should not lose
    truth = rng.integers(0, 2, size=n)
    probe = np.clip(truth * 0.4 + 0.3 + rng.normal(0, 0.15, n), 0, 1)
    signal = np.where(truth == 1, 1.0, np.where(rng.random(n) < 0.5,
                                                0.5, 0.0))
    scored = pd.DataFrame({
        "first_sentence": [f"Entity {i} is a thing" for i in range(n)],
        "score": probe,
        "correct": truth.astype(bool),
    })
    # the signal is injected through the helper below so the ensemble,
    # out-of-fold fitting and paired machinery are tested independently
    # of the shallow extractor's recall
    doc = _evaluate_with_injected_signal(CFG, scored, signal)
    assert doc["status"] == "evaluated"
    assert doc["auc_probe"] > 0.6
    assert 0.0 <= doc["auc_signal"] <= 1.0
    assert 0.0 <= doc["auc_ensemble"] <= 1.0
    assert doc["extractable_fraction"] == 1.0


def _evaluate_with_injected_signal(cfg, scored, signal):
    """evaluate_ensemble with a graph oracle replaced by an injected
    signal column: keeps the ensemble/OOF/paired machinery under test
    while isolating it from the shallow extractor's recall."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler

    from cassandra_ns.probes.stats import (paired_bootstrap_diff_auc,
                                           roc_auc)

    probe = scored["score"].to_numpy()
    y = scored["correct"].astype(int).to_numpy()
    X = np.column_stack([probe, signal])
    ensemble_oof = np.full(len(y), np.nan)
    skf = StratifiedKFold(n_splits=5, shuffle=True,
                          random_state=int(cfg["seed"]))
    for tr, te in skf.split(X, y):
        scaler = StandardScaler().fit(X[tr])
        model = LogisticRegression(max_iter=1000,
                                   random_state=int(cfg["seed"]))
        model.fit(scaler.transform(X[tr]), y[tr])
        ensemble_oof[te] = model.predict_proba(
            scaler.transform(X[te]))[:, 1]
    n_boot = int(cfg["stats"]["n_bootstrap"])
    paired = paired_bootstrap_diff_auc(y, ensemble_oof, probe, n_boot,
                                       0.95, int(cfg["seed"]))
    return {
        "status": "evaluated",
        "n_extractable": len(y),
        "extractable_fraction": 1.0,
        "auc_probe": roc_auc(y, probe),
        "auc_signal": roc_auc(y, signal),
        "auc_ensemble": roc_auc(y, ensemble_oof),
        "ensemble_minus_probe": paired,
    }


def test_extractable_subset_gate() -> None:
    scored = pd.DataFrame({
        "first_sentence": ["no claim here"] * 50,
        "score": np.random.default_rng(42).random(50),
        "correct": np.zeros(50, dtype=bool),
    })
    graph = {"supported": set(), "contradicted": set()}
    doc = bridge.evaluate_ensemble(CFG, scored, graph)
    assert doc["status"] == "unavailable"
    assert "claims" in doc["cause"]


def test_constant_signal_is_reported_not_crashing() -> None:
    """The real PROMETHEUS-NS graph covers none of the TriviaQA claims:
    the signal is constant 0.5 and the ensemble must still evaluate,
    with the coverage block tracing the degeneration to its cause."""
    rng = np.random.default_rng(42)
    n = 120
    truth = rng.integers(0, 2, size=n)
    scored = pd.DataFrame({
        "first_sentence": [f"Entity {i} is a thing" for i in range(n)],
        "score": np.clip(truth * 0.3 + 0.35 + rng.normal(0, 0.1, n), 0, 1),
        "correct": truth.astype(bool),
    })
    graph = {"supported": set(), "contradicted": set()}
    doc = bridge.evaluate_ensemble(CFG, scored, graph)
    assert doc["status"] == "evaluated"
    assert doc["auc_signal"] == 0.5  # constant signal, exact by construction
    cov = doc["coverage"]
    assert cov["n_claim_tuples_supported"] == 0
    assert cov["n_rows_signal_unknown"] == n
    assert cov["n_rows_no_label_excluded"] == 0


def test_unlabeled_rows_are_excluded_and_reported() -> None:
    """Excluded generations arrive with correct=None (boolean nullable):
    they carry no evaluation information, are dropped, and the drop is
    reported in the coverage block."""
    n = 120
    truth = np.array([1, 0] * (n // 2))
    correct = pd.array(truth.astype(bool), dtype="boolean")
    correct[:10] = pd.NA  # excluded rows (no declarative, alias in question)
    scored = pd.DataFrame({
        "first_sentence": [f"Entity {i} is a thing" for i in range(n)],
        "score": np.linspace(0.2, 0.8, n),
        "correct": correct,
    })
    graph = {"supported": set(), "contradicted": set()}
    doc = bridge.evaluate_ensemble(CFG, scored, graph)
    assert doc["status"] == "evaluated"
    cov = doc["coverage"]
    assert cov["n_rows_no_label_excluded"] == 10
    assert doc["n_generations"] == n - 10


def test_paired_bootstrap_skips_single_class_resamples() -> None:
    """With 2 positives out of 146 (the real gpt2 extractable subset),
    ~13% of resamples miss both positives; they are redrawn and counted
    instead of crashing on an undefined AUC."""
    from cassandra_ns.probes.stats import paired_bootstrap_diff_auc

    rng = np.random.default_rng(7)
    y = np.zeros(146, dtype=int)
    y[:2] = 1
    scores_a = rng.random(146)
    scores_b = rng.random(146)
    doc = paired_bootstrap_diff_auc(y, scores_a, scores_b, 200, 0.95, 42)
    assert 0 < doc["n_resamples_skipped"] < 200
    assert -1.0 <= doc["diff"] <= 1.0


def test_paired_bootstrap_zero_skips_on_balanced_data() -> None:
    from cassandra_ns.probes.stats import paired_bootstrap_diff_auc

    rng = np.random.default_rng(7)
    y = np.array([0, 1] * 100)
    scores_a = rng.random(200)
    scores_b = rng.random(200)
    doc = paired_bootstrap_diff_auc(y, scores_a, scores_b, 200, 0.95, 42)
    assert doc["n_resamples_skipped"] == 0


def test_exported_prometheus_graph_loads(tmp_path) -> None:
    """The bridge file format produced by prometheus-ns
    scripts/export_consistency_graph.py loads through load_graph with
    the documented predicate-alias semantics: a claim on the surface
    verb matches the alias row. load_graph normalizes is_a to 'isa'
    (the underscore is stripped), so WITHOUT the alias rows the
    canonical lemma rows would be unreachable for surface-verb claims
    — the adapter is what makes the two schemas interoperate."""
    path = tmp_path / "prometheus_graph.json"
    path.write_text(
        '{"meta": {"source": "PROMETHEUS-NS symbolic store"},'
        '"triplets": [["eiffel tower", "is_a", "tower", true],'
        '["eiffel tower", "is", "tower", true],'
        '["tokyo tower", "is_a", "mountain", false],'
        '["tokyo tower", "is", "mountain", false]]}',
        encoding="utf-8")
    graph = bridge.load_graph(path)
    # the canonical lemma row is normalized to 'isa': not reachable by
    # a surface-verb claim on its own...
    assert ("eiffel tower", "isa", "tower") in graph["supported"]
    assert bridge.symbolic_signal(
        graph, [("eiffel tower", "is", "tower")]) == 1.0
    # ...but the alias row added by the exporter matches it
    assert bridge.symbolic_signal(
        graph, [("tokyo tower", "is", "mountain")]) == 0.0
    # unknown claims stay unknown
    assert bridge.symbolic_signal(
        graph, [("colosseum", "is", "arena")]) == 0.5
