"""Probe training with grouped cross-validation.

For every (model, layer, mode, probe type) combination:

- the StandardScaler is fitted inside each training fold, never
  globally (scaler leakage would filter test-fold statistics);
- logistic regression selects C over config.probes.C_grid by an inner
  StratifiedGroupKFold on the training folds only (groups = entity),
  then refits on the full training folds;
- the MLP (one hidden layer of config.probes.mlp_hidden units) uses
  early stopping on an internal validation split, seed 42;
- every test fold receives exactly one out-of-fold prediction per
  statement, appended to logs/oof_predictions.jsonl together with the
  model's own |mean logprob| baseline for the paired comparison.

The baseline is a comparison anchor, never a probe feature. OOF rows
are appended per configuration, so an interrupted grid resumes where
it stopped (existing complete configurations are skipped).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler

from cassandra_ns.activations.cache import load_logprobs, load_vectors
from cassandra_ns.data.splits import fold_of_map
from cassandra_ns.probes.stats import roc_auc


def oof_path(cfg: dict) -> Path:
    return Path("logs") / "oof_predictions.jsonl"


def _load_existing_configs(path: Path) -> set[tuple]:
    done: set[tuple] = set()
    if not path.is_file():
        return done
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            done.add((row["model"], int(row["layer"]), row["mode"],
                      row["ptype"]))
    return done


def _make_probe(ptype: str, C: float, hidden: int, seed: int):
    if ptype == "logistic":
        return LogisticRegression(C=C, max_iter=2000, solver="lbfgs",
                                  random_state=seed)
    if ptype == "mlp":
        return MLPClassifier(hidden_layer_sizes=(hidden,),
                             early_stopping=True, validation_fraction=0.1,
                             n_iter_no_change=10, max_iter=200,
                             random_state=seed, activation="relu",
                             solver="adam", alpha=1e-4)
    raise ValueError(f"unknown probe type: {ptype}")


def _select_C(X_train: np.ndarray, y_train: np.ndarray,
              groups_train: np.ndarray, strata_train: np.ndarray,
              C_grid: list[float], seed: int) -> tuple[float, dict]:
    """Inner grouped CV over the training folds only; deterministic."""
    inner = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=seed)
    splits = list(inner.split(X_train, y=strata_train, groups=groups_train))
    scores: dict[float, float] = {}
    for C in C_grid:
        fold_aucs: list[float] = []
        for tr, te in splits:
            if len(np.unique(y_train[te])) < 2:
                continue
            scaler = StandardScaler().fit(X_train[tr])
            probe = _make_probe("logistic", C, 64, seed)
            probe.fit(scaler.transform(X_train[tr]), y_train[tr])
            proba = probe.predict_proba(scaler.transform(X_train[te]))[:, 1]
            fold_aucs.append(roc_auc(y_train[te], proba))
        scores[C] = float(np.mean(fold_aucs)) if fold_aucs else 0.0
    best_C = max(C_grid, key=lambda c: (scores[c], -C_grid.index(c)))
    return float(best_C), scores


def _train_one(cfg: dict, model: str, layer: int, mode: str,
               ptype: str, vectors: np.ndarray, df: pd.DataFrame,
               fold_of: dict[str, int], n_folds: int,
               baseline: np.ndarray) -> list[dict]:
    """Train one configuration over all folds; return OOF rows."""
    seed = int(cfg["seed"])
    y_all = df["label"].astype(bool).astype(int).to_numpy()
    strata_all = (df["domain"].astype(str) + "|"
                  + df["label"].astype(bool).astype(int).astype(str)).to_numpy()
    groups_all = df["entity"].to_numpy()
    fold_arr = df["id"].map(fold_of).to_numpy()

    X = np.asarray(vectors, dtype=np.float32)
    oof_prob = np.full(len(df), np.nan, dtype=np.float64)

    for k in range(n_folds):
        train_mask = fold_arr != k
        test_mask = fold_arr == k
        scaler = StandardScaler().fit(X[train_mask])
        X_train = scaler.transform(X[train_mask])
        y_train = y_all[train_mask]
        if ptype == "logistic":
            C, _scores = _select_C(
                X_train, y_train, groups_all[train_mask],
                strata_all[train_mask], cfg["probes"]["C_grid"], seed)
            probe = _make_probe("logistic", C, cfg["probes"]["mlp_hidden"],
                                seed)
        else:
            probe = _make_probe("mlp", 1.0, cfg["probes"]["mlp_hidden"],
                                seed)
        probe.fit(X_train, y_train)
        oof_prob[test_mask] = probe.predict_proba(
            scaler.transform(X[test_mask]))[:, 1]

    if np.isnan(oof_prob).any():
        missing = int(np.isnan(oof_prob).sum())
        raise RuntimeError(
            f"{model}/{layer}/{mode}/{ptype}: {missing} statements "
            "without an out-of-fold prediction")

    rows = []
    for i in range(len(df)):
        rows.append({
            "id": df["id"].iloc[i],
            "model": model,
            "layer": int(layer),
            "mode": mode,
            "ptype": ptype,
            "fold": int(fold_arr[i]),
            "y_true": int(y_all[i]),
            "score": float(oof_prob[i]),
            "baseline": float(baseline[i]),
        })
    return rows


def train_all_probes(cfg: dict, models: list[str] | None = None) -> Path:
    """Run the full pre-registered grid; append to the OOF log.

    Family = {layers x feature modes x probe types} per model, fixed in
    advance by config.yaml - never extended after seeing results.
    """
    from cassandra_ns.config import model_layers
    from cassandra_ns.data.loader import load_processed

    seed = int(cfg["seed"])
    out = oof_path(cfg)
    out.parent.mkdir(parents=True, exist_ok=True)
    done_configs = _load_existing_configs(out)

    df = load_processed(cfg)
    fold_of = fold_of_map(load_folds_for(cfg))
    n_folds = int(cfg["splits"]["n_folds"])

    for model in models or [m["name"] for m in cfg["models"]]:
        layers = model_layers(cfg, model)
        baseline_df = load_logprobs(cfg, model)
        baseline_df = baseline_df.set_index("id").loc[df["id"]]
        baseline = np.abs(baseline_df["mean_logprob"].to_numpy())

        for layer in layers:
            for mode in cfg["probes"]["feature_modes"]:
                vectors = load_vectors(cfg, model, layer, mode)
                vectors = np.asarray(vectors, dtype=np.float32)
                for ptype in cfg["probes"]["types"]:
                    key = (model, int(layer), mode, ptype)
                    if key in done_configs:
                        print(f"  = {key}: OOF rows already present")
                        continue
                    rows = _train_one(cfg, model, int(layer), mode, ptype,
                                      vectors, df, fold_of, n_folds,
                                      baseline)
                    with out.open("a", encoding="utf-8") as fh:
                        for row in rows:
                            fh.write(json.dumps(row) + "\n")
                    print(f"  + {key}: {len(rows)} OOF rows written")
    return out


def load_folds_for(cfg: dict) -> dict:
    from cassandra_ns.data.splits import load_folds
    return load_folds(cfg)
