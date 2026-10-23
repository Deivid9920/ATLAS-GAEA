"""Optional symbolic bridge to the PROMETHEUS-NS consistency graph.

Contract: when config.ensemble.prometheus_graph points to a
consistency-graph JSON, subject-predicate-object triplets are extracted
from the generations' first declarative sentences, mapped to a symbolic
signal in {0, 0.5, 1} by graph consistency, and combined with the probe
score through a 2-feature logistic regression fitted inside
cross-validation folds of the extractable subset only (never on the
evaluation rows). The comparison - probe alone vs symbolic signal
alone vs ensemble - is reported on the SAME extractable subset with a
paired bootstrap. If the ensemble does not improve, that is the
reported finding.

Without a graph the ensemble is marked "unavailable" with its cause
(the anchor config ships prometheus_graph: null) and everything else
still runs.

Graph file format (exported by PROMETHEUS-NS from its symbolic store):

  {"triplets": [["paris", "located_in", "france", true],
                ["paris", "located_in", "germany", false], ...]}

lowercase normalized head/tail, boolean consistency. Triplets absent
from the graph count as 0.5 (unknown).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

_VERBS = ("is", "are", "was", "were", "invented", "discovered",
          "wrote", "located", "born", "died", "lived", "founded")


def extract_triplets(sentence: str) -> list[tuple[str, str, str]]:
    """Simple is_a-style claims: <subject> <verb> <object>.

    A deliberately shallow extractor: first NP before a linking verb,
    complement after it, normalized to lowercase tokens. The point is
    a bounded, auditable claim set, not open information extraction.
    """
    import re

    text = sentence.strip().rstrip(".!?").strip()
    claims: list[tuple[str, str, str]] = []
    if "?" in sentence:
        return claims  # questions are never claims
    for verb in _VERBS:
        pattern = re.compile(
            r"^(?P<subj>[A-Z][\w'\-]*(?:\s+[\w'\-]+){0,3}?)\s+"
            + verb + r"\s+(?P<obj>.{3,60})$", flags=re.IGNORECASE)
        match = pattern.match(text)
        if match:
            subj = _norm_np(match.group("subj"))
            obj = _norm_np(match.group("obj"))
            if subj and obj:
                claims.append((subj, verb.lower(), obj))
            break
    return claims


def _norm_np(np_text: str) -> str:
    import re

    text = re.sub(r"^(the|a|an)\s+", "", np_text.strip().lower())
    text = re.sub(r"[^a-z0-9\s\-]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def load_graph(path: str | Path) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if "triplets" not in doc:
        raise ValueError(
            f"{path}: consistency graph must contain a 'triplets' list")
    supported: set[tuple[str, str, str]] = set()
    contradicted: set[tuple[str, str, str]] = set()
    for triplet in doc["triplets"]:
        s, p, o = _norm_np(str(triplet[0])), _norm_np(str(triplet[1])), \
            _norm_np(str(triplet[2]))
        consistent = bool(triplet[3]) if len(triplet) > 3 else True
        (supported if consistent else contradicted).add((s, p, o))
    return {"supported": supported, "contradicted": contradicted}


def symbolic_signal(graph: dict, claims: list[tuple[str, str, str]]
                    ) -> float:
    """{0, 0.5, 1}: 1 when some claim is supported and none is
    contradicted; 0 when some claim is contradicted; 0.5 otherwise
    (unknown or no claims)."""
    if not claims:
        return 0.5
    if any(c in graph["contradicted"] for c in claims):
        return 0.0
    if any(c in graph["supported"] for c in claims):
        return 1.0
    return 0.5


def evaluate_ensemble(cfg: dict, scored: pd.DataFrame, graph: dict
                      ) -> dict:
    """Probe vs signal vs ensemble on the same extractable subset.

    The 2-feature logistic ensemble is fitted out-of-fold (5-fold,
    seed 42) inside the extractable subset, so every row carries an
    out-of-fold ensemble score; the paired bootstrap compares the
    three systems on identical rows.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler

    from cassandra_ns.probes.stats import (paired_bootstrap_diff_auc,
                                           roc_auc)

    # rows without a ground-truth label (excluded generations: no
    # declarative sentence, alias contained in the question) carry no
    # evaluation information; they are dropped and the drop is
    # reported, never silently forced to any class
    n_no_label = int(scored["correct"].isna().sum())
    scored = scored[scored["correct"].notna()].reset_index(drop=True)
    if scored["score"].isna().any():
        raise ValueError("scored rows with NaN probe score: the "
                         "ensemble requires a finite score per row")
    sentences = scored["first_sentence"].tolist()
    claims_per_row = [extract_triplets(s) for s in sentences]
    extractable = [i for i, c in enumerate(claims_per_row) if c]
    n_total = len(scored)
    if len(extractable) < 40:
        return {"status": "unavailable",
                "cause": f"only {len(extractable)} of {n_total} "
                         "generations produced is_a-style claims "
                         "(need >= 40 for a meaningful comparison)"}

    sub = scored.iloc[extractable].reset_index(drop=True)
    sub_claims = [claims_per_row[i] for i in extractable]
    signal = np.array([symbolic_signal(graph, c) for c in sub_claims])
    probe = sub["score"].to_numpy()
    y = sub["correct"].astype(int).to_numpy()

    # coverage statistics of the graph over the extracted claims: the
    # bridge reports how much of the claim space the graph actually
    # knows, because an ensemble over a ~unknown signal degenerates to
    # the probe and that finding must be traceable to its cause
    n_claim_tuples = sum(len(c) for c in sub_claims)
    n_supported_tuples = sum(1 for c in sub_claims
                             for t in c if t in graph["supported"])
    n_contradicted_tuples = sum(1 for c in sub_claims
                                for t in c if t in graph["contradicted"])
    graph_subjects = {t[0] for t in graph["supported"] | graph["contradicted"]}
    row_subjects = {c[0][0] for c in sub_claims if c}
    signal_values, signal_counts = np.unique(signal, return_counts=True)
    coverage = {
        "n_rows_no_label_excluded": n_no_label,
        "n_rows_extractable": len(sub),
        "n_claim_tuples": n_claim_tuples,
        "n_claim_tuples_supported": n_supported_tuples,
        "n_claim_tuples_contradicted": n_contradicted_tuples,
        "n_claim_tuples_unknown": n_claim_tuples - n_supported_tuples
                                  - n_contradicted_tuples,
        "n_rows_signal_supported": int(signal_counts[signal_values == 1.0][0])
                                   if 1.0 in signal_values else 0,
        "n_rows_signal_contradicted": int(signal_counts[signal_values == 0.0][0])
                                      if 0.0 in signal_values else 0,
        "n_rows_signal_unknown": int(signal_counts[signal_values == 0.5][0])
                                 if 0.5 in signal_values else 0,
        "graph_supported_rows": len(graph["supported"]),
        "graph_contradicted_rows": len(graph["contradicted"]),
        "graph_unique_subjects": len(graph_subjects),
        "claim_subjects_in_graph": len(row_subjects & graph_subjects),
        "claim_subjects_total": len(row_subjects),
    }

    # out-of-fold ensemble scores: the 2-feature model never sees the
    # row it scores
    X = np.column_stack([probe, signal])
    ensemble_oof = np.full(len(sub), np.nan)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=
                          int(cfg["seed"]))
    for tr, te in skf.split(X, y):
        scaler = StandardScaler().fit(X[tr])
        model = LogisticRegression(max_iter=1000,
                                   random_state=int(cfg["seed"]))
        model.fit(scaler.transform(X[tr]), y[tr])
        ensemble_oof[te] = model.predict_proba(
            scaler.transform(X[te]))[:, 1]

    n_boot = int(cfg["stats"]["n_bootstrap"])
    ci = float(cfg["stats"]["ci"])
    seed = int(cfg["seed"])
    auc_probe = roc_auc(y, probe)
    auc_signal = roc_auc(y, signal)
    auc_ensemble = roc_auc(y, ensemble_oof)
    paired_e_p = paired_bootstrap_diff_auc(y, ensemble_oof, probe,
                                           n_boot, ci, seed)
    paired_p_s = paired_bootstrap_diff_auc(y, probe, signal,
                                           n_boot, ci, seed)
    return {
        "status": "evaluated",
        "n_generations": n_total,
        "n_extractable": len(sub),
        "extractable_fraction": len(sub) / n_total,
        "auc_probe": auc_probe,
        "auc_signal": auc_signal,
        "auc_ensemble": auc_ensemble,
        "ensemble_minus_probe": paired_e_p,
        "probe_minus_signal": paired_p_s,
        "coverage": coverage,
        "note": "the comparison holds for the extractable is_a subset "
                "only, not for all generations",
    }


def load_ensemble_results(cfg: dict) -> dict:
    """The ensemble evaluation record (evaluated or unavailable)."""
    path = Path("logs") / "ensemble_results.json"
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found: run `make ensemble` first")
    return json.loads(path.read_text(encoding="utf-8"))


def _self_test() -> None:
    """Synthetic-graph verification of the bridge contract."""
    g = {"supported": {("paris", "is", "a city"), ("iron", "is", "a metal")},
         "contradicted": {("paris", "is", "a country")}}
    assert symbolic_signal(g, [("paris", "is", "a city")]) == 1.0
    assert symbolic_signal(g, [("paris", "is", "a country")]) == 0.0
    assert symbolic_signal(g, [("rome", "is", "a city")]) == 0.5
    assert symbolic_signal(g, []) == 0.5
    claims = extract_triplets("Paris is the capital of France")
    assert claims, "extractor found no claims in a simple is_a sentence"
    print("symbolic bridge self-test: ok "
          f"({len(claims)} claim(s) from the sample sentence)")


if __name__ == "__main__":
    _self_test()
