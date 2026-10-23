"""Probe evaluation: honest aggregation of out-of-fold predictions.

Produces:

- logs/probe_results.jsonl: one row per (model, layer, mode, ptype)
  overall (domain = null) plus one row per domain; overall rows carry
  AUC with bootstrap CI, AP, ECE, Brier, and the paired bootstrap of
  AUC(probe) - AUC(|logprob|) with its own CI and p-value (the same
  partition, the correlation between systems preserved);
- docs/probe_table.md: the human-readable table;
- logs/lodo_results.json: leave-one-domain-out secondary analysis for
  the best configuration of each model (train on 5 domains, evaluate
  on the held-out one - the honest OOD picture);
- logs/tfidf_control.json: the stylistic-confound control (a logistic
  probe over TF-IDF bag-of-words under the same grouped folds; if it
  rivals the neural probes, the signal is lexical, not mechanistic);
- logs/style_pairs.json: control on same-subject true/false pairs;
- logs/leakage_audit.md: the mandatory audit whenever an AUC exceeds
  0.95 (expected: never; literature reports 0.70-0.85 mid-layer).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from cassandra_ns.data.splits import fold_of_map, load_folds
from cassandra_ns.probes.calibration import brier, ece
from cassandra_ns.probes.stats import (bootstrap_ci, holm_bonferroni,
                                       paired_bootstrap_diff_auc, roc_auc)


def results_path(cfg: dict) -> Path:
    return Path("logs") / "probe_results.jsonl"


def load_oof(cfg: dict) -> pd.DataFrame:
    path = Path("logs") / "oof_predictions.jsonl"
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found: run `make probe` first")
    rows = [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise RuntimeError(f"{path} is empty: run `make probe` first")
    return pd.DataFrame(rows)


def load_results(cfg: dict) -> pd.DataFrame:
    path = results_path(cfg)
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found: run `make report` first")
    rows = [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        raise RuntimeError(f"{path} is empty: run `make report` first")
    return pd.DataFrame(rows)


def _one_row(y: np.ndarray, score: np.ndarray, base: np.ndarray,
             stats_cfg: dict, seed: int, domain) -> dict:
    n_boot = int(stats_cfg["n_bootstrap"])
    ci = float(stats_cfg["ci"])
    auc, lo, hi = bootstrap_ci(y, score, roc_auc, n_boot, ci, seed)
    paired = paired_bootstrap_diff_auc(y, score, base, n_boot, ci, seed)
    return {
        "n": int(len(y)),
        "auc": auc, "ci_lo": lo, "ci_hi": hi,
        "ap": average_precision(y, score),
        "ece": ece(y, score), "brier": brier(y, score),
        "p_baseline": paired["p_two_sided"],
        "diff": paired["diff"], "diff_lo": paired["lo"],
        "diff_hi": paired["hi"],
        "domain": domain,
    }


def _recall_precision(y, score):
    """(recall, precision) curves for the AP placeholder path."""
    from sklearn.metrics import precision_recall_curve
    prec, rec, _ = precision_recall_curve(y, score)
    return rec, prec


def average_precision(y: np.ndarray, score: np.ndarray) -> float:
    from sklearn.metrics import average_precision_score
    return float(average_precision_score(y, score))


def _baseline_auc(y: np.ndarray, base: np.ndarray) -> float:
    try:
        return roc_auc(y, base)
    except ValueError:
        return float("nan")


def aggregate(cfg: dict) -> pd.DataFrame:
    """Aggregate OOF rows into the probe results table.

    Incremental: overall + per-domain rows are appended per
    configuration as soon as they are computed, and configurations
    already present in the results file are skipped, so a long
    bootstrap aggregation survives interruptions without recomputing.
    """
    from cassandra_ns.data.loader import load_processed

    seed = int(cfg["seed"])
    oof = load_oof(cfg)
    df = load_processed(cfg)[["id", "domain"]]
    oof = oof.merge(df, on="id", how="left")

    out_path = results_path(cfg)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existing: set[tuple] = set()
    if out_path.is_file():
        with out_path.open(encoding="utf-8") as fh:
            for line in fh:
                row = json.loads(line)
                existing.add((row["model"], int(row["layer"]), row["mode"],
                              row["ptype"], row.get("domain")))

    group_cols = ["model", "layer", "mode", "ptype"]
    results: list[dict] = []
    with out_path.open("a", encoding="utf-8") as fh:
        for key, group in oof.groupby(group_cols, sort=True):
            model, layer, mode, ptype = key
            y = group["y_true"].to_numpy().astype(int)
            score = group["score"].to_numpy()
            base = group["baseline"].to_numpy()

            overall_rows = existing and (model, int(layer), mode, ptype,
                                         None) in existing
            if not overall_rows:
                row = {"model": model, "layer": int(layer), "mode": mode,
                       "ptype": ptype,
                       "baseline_auc": _baseline_auc(y, base),
                       **_one_row(y, score, base, cfg["stats"], seed,
                                  None)}
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                results.append(row)
                print(f"  + {key}: overall AUC {row['auc']:.3f} "
                      f"[{row['ci_lo']:.3f}, {row['ci_hi']:.3f}]",
                      flush=True)
            for domain, dgroup in group.groupby("domain"):
                if (model, int(layer), mode, ptype, domain) in existing:
                    continue
                yd = dgroup["y_true"].to_numpy().astype(int)
                if len(np.unique(yd)) < 2:
                    continue
                drow = {"model": model, "layer": int(layer),
                        "mode": mode, "ptype": ptype,
                        "baseline_auc": _baseline_auc(
                            yd, dgroup["baseline"].to_numpy()),
                        **_one_row(yd, dgroup["score"].to_numpy(),
                                   dgroup["baseline"].to_numpy(),
                                   cfg["stats"], seed, domain)}
                fh.write(json.dumps(drow) + "\n")
                fh.flush()

    table = pd.DataFrame(results)
    if out_path.is_file():
        all_rows = [json.loads(line) for line in
                    out_path.read_text(encoding="utf-8").splitlines()
                    if line]
        table = pd.DataFrame(all_rows)
    return table


def leakage_audit(cfg: dict, table: pd.DataFrame) -> Path | None:
    """Mandatory audit when an AUC exceeds 0.95."""
    suspects = table[(table["domain"].isna())
                     & (table["auc"] > 0.95)]
    if suspects.empty:
        return None
    path = Path("logs") / "leakage_audit.md"
    lines = [
        "# Mandatory leakage audit (triggered by AUC > 0.95)",
        "",
        "Expectation from the literature: AUC 0.70-0.85 in mid layers.",
        "An AUC above 0.95 is treated as a split bug until proven "
        "otherwise. Checks below.",
        "",
    ]
    for _, r in suspects.iterrows():
        lines.append(
            f"- {r['model']} layer {r['layer']} {r['mode']}/{r['ptype']}: "
            f"AUC {r['auc']:.4f}")
    lines += [
        "",
        "1. Entity grouping check: rebuild folds, count entities shared "
        "between train and test per fold (expected 0).",
        "2. Scaler check: confirm the scaler statistics come from the "
        "training folds only.",
        "3. Duplicated statements check: exact duplicates across folds.",
        "",
        "The audit runs on demand: rebuild folds and re-run make probe; "
        "if the AUC persists above 0.95 with clean splits, document why "
        "before any claim.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def leave_one_domain_out(cfg: dict) -> Path:
    """Secondary analysis: train on 5 domains, evaluate on the 6th."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from cassandra_ns.config import load_config, model_layers  # noqa: F401
    from cassandra_ns.data.loader import load_processed
    from cassandra_ns.activations.cache import load_vectors

    seed = int(cfg["seed"])
    df = load_processed(cfg)
    y = df["label"].astype(bool).astype(int).to_numpy()
    domains = sorted(df["domain"].unique())
    results = {}
    oof = load_oof(cfg)

    for model in [m["name"] for m in cfg["models"]]:
        # best configuration of this model by overall AUC
        overall = (oof[(oof["model"] == model)]
                   .groupby(["layer", "mode", "ptype"])
                   .apply(lambda g: roc_auc(g["y_true"], g["score"]))
                   .sort_values(ascending=False))
        layer, mode, ptype = overall.index[0]
        vectors = np.asarray(
            load_vectors(cfg, model, int(layer), mode), dtype=np.float32)
        in_domain, out_domain = [], []
        for held_out in domains:
            train_mask = (df["domain"] != held_out).to_numpy()
            test_mask = ~train_mask
            scaler = StandardScaler().fit(vectors[train_mask])
            probe = LogisticRegression(max_iter=2000, random_state=seed)
            probe.fit(scaler.transform(vectors[train_mask]), y[train_mask])
            scores = probe.predict_proba(
                scaler.transform(vectors[test_mask]))[:, 1]
            auc = roc_auc(y[test_mask], scores)
            results.setdefault(str(layer), {})[held_out] = {
                "mode": mode, "ptype": ptype, "auc_ood": auc}
            in_domain.append(overall.iloc[0])
            out_domain.append(auc)
        results[str(layer)]["_meta"] = {
            "model": model, "layer": int(layer), "mode": mode,
            "ptype": ptype,
            "mean_auc_in_domain": float(np.mean(in_domain)),
            "mean_auc_out_of_domain": float(np.mean(out_domain)),
        }
    path = Path("logs") / "lodo_results.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return path


def tfidf_control(cfg: dict) -> Path:
    """Stylistic confound control: TF-IDF probe under the same folds."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler  # noqa: F401
    from scipy.sparse import spmatrix  # noqa: F401
    from cassandra_ns.data.loader import load_processed

    seed = int(cfg["seed"])
    df = load_processed(cfg)
    y = df["label"].astype(bool).astype(int).to_numpy()
    fold_of = fold_of_map(load_folds(cfg))
    fold_arr = df["id"].map(fold_of).to_numpy()

    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    X = vec.fit_transform(df["statement"])
    oof = np.full(len(df), np.nan)
    for k in sorted(set(fold_arr)):
        tr, te = fold_arr != k, fold_arr == k
        probe = LogisticRegression(C=1.0, max_iter=2000,
                                   random_state=seed)
        probe.fit(X[tr], y[tr])
        oof[te] = probe.predict_proba(X[te])[:, 1]

    auc = roc_auc(y, oof)
    _, lo, hi = bootstrap_ci(y, oof, roc_auc,
                             int(cfg["stats"]["n_bootstrap"]),
                             float(cfg["stats"]["ci"]), seed)
    path = Path("logs") / "tfidf_control.json"
    path.write_text(json.dumps({
        "auc": auc, "ci_lo": lo, "ci_hi": hi,
        "note": "bag-of-words (TF-IDF 1-2 grams) logistic under the "
                "same entity-grouped folds; comparable AUC to the "
                "neural probes would indicate a lexical, not "
                "mechanistic, signal"}, indent=2), encoding="utf-8")
    return path


def style_pairs_control(cfg: dict) -> Path:
    """Control on minimal pairs: same subject, same template, opposite
    truth. AUC restricted to the detected pairs, with the pair count
    reported - a small-sample control, never the headline number."""
    from cassandra_ns.data.loader import load_processed
    from cassandra_ns.activations.cache import load_vectors
    from cassandra_ns.config import model_layers

    seed = int(cfg["seed"])
    df = load_processed(cfg)
    neg_words = [" not ", " no ", "n't ", " never "]
    pairs: list[tuple[int, int]] = []
    by_entity = df.groupby(["domain", "entity"]).groups
    for (_domain, _entity), idx in by_entity.items():
        idx = list(idx)
        trues = [i for i in idx if bool(df["label"].iloc[i])]
        falses = [i for i in idx if not bool(df["label"].iloc[i])]
        for i in trues:
            s_i = df["statement"].iloc[i].lower()
            for j in falses:
                s_j = df["statement"].iloc[j].lower()
                if abs(len(s_i) - len(s_j)) > 25:
                    continue
                shorter, longer = (s_i, s_j) if len(s_i) < len(s_j) \
                    else (s_j, s_i)
                if not any(w in longer for w in neg_words):
                    continue
                stripped = longer
                for w in neg_words:
                    stripped = stripped.replace(w, " ")
                if shorter[:20] == stripped[:20].strip()[:20] or \
                        shorter[-20:] == stripped[-20:].strip()[-20:]:
                    pairs.append((i, j))
                    break

    if not pairs:
        path = Path("logs") / "style_pairs.json"
        path.write_text(json.dumps({"n_pairs": 0,
                                    "note": "no minimal pairs detected"},
                                   indent=2), encoding="utf-8")
        return path

    oof = load_oof(cfg)
    results = {}
    for model in [m["name"] for m in cfg["models"]]:
        best = (oof[(oof["model"] == model)]
                .groupby(["layer", "mode", "ptype"])
                .apply(lambda g: roc_auc(g["y_true"], g["score"]))
                .sort_values(ascending=False))
        layer, mode, ptype = best.index[0]
        scores = oof[(oof["model"] == model) & (oof["layer"] == layer)
                     & (oof["mode"] == mode) & (oof["ptype"] == ptype)]
        scores = scores.set_index("id").loc[df["id"]]
        s = scores["score"].to_numpy()
        i_idx = [i for i, _ in pairs]
        j_idx = [j for _, j in pairs]
        y_pair = np.concatenate([np.ones(len(i_idx), dtype=int),
                                 np.zeros(len(j_idx), dtype=int)])
        s_pair = np.concatenate([s[i_idx], s[j_idx]])
        auc = roc_auc(y_pair, s_pair)
        results[model] = {"layer": int(layer), "mode": mode,
                          "ptype": ptype, "n_pairs": len(pairs),
                          "auc_pairs": auc}
    path = Path("logs") / "style_pairs.json"
    path.write_text(json.dumps({"n_pairs": len(pairs), "models": results},
                               indent=2), encoding="utf-8")
    return path


def write_probe_table_md(cfg: dict, table: pd.DataFrame) -> Path:
    """docs/probe_table.md: the full grid with CIs and significance."""
    overall = table[table["domain"].isna()].copy()
    overall = overall.sort_values(["model", "auc"], ascending=[True, False])
    family = overall.reset_index(drop=True)
    family["p_holm"] = holm_bonferroni(family["p_baseline"].tolist())

    lines = [
        "# Probe results (grouped 5-fold CV by entity, seed 42)",
        "",
        "AUC with 95% percentile-bootstrap CI; the paired columns "
        "compare AUC(probe) against AUC(|mean logprob|) of the same "
        "model on the same out-of-fold partition.",
        "",
        "| model | layer | mode | probe | AUC [CI] | AP | ECE | Brier "
        "| p paired | p Holm |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for (_, r), p_h in zip(family.iterrows(), family["p_holm"]):
        lines.append(
            f"| {r['model']} | {r['layer']} | {r['mode']} | "
            f"{r['ptype']} | {r['auc']:.3f} "
            f"[{r['ci_lo']:.3f}, {r['ci_hi']:.3f}] | {r['ap']:.3f} | "
            f"{r['ece']:.3f} | {r['brier']:.3f} | "
            f"{r['p_baseline']:.4f} | {p_h:.4f} |")
    path = Path("docs") / "probe_table.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
