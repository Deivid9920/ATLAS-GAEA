"""Grouped splits for CASSANDRA: the anti-leakage anchor.

StratifiedGroupKFold with groups = entity and stratification =
(domain, label), n_folds fixed folds written to
data/processed/folds.json together with the sha256 of the assignment.
A statement never appears in two folds; rebuilding with the same seed
reproduces the file byte for byte. The builder verifies its own output
(group integrity + per-fold class coverage) and fails loudly rather
than writing a leaking partition.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold


def folds_path(cfg: dict) -> Path:
    return Path(cfg["data"]["cache_dir"]) / "folds.json"


def _assignment_sha256(folds: list[dict]) -> str:
    payload = json.dumps(
        [[f["fold"], sorted(f["test_ids"])] for f in folds],
        sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_folds(cfg: dict, df: pd.DataFrame) -> dict:
    """Build the fixed folds and write folds.json with its sha256."""
    n_folds = int(cfg["splits"]["n_folds"])
    seed = int(cfg["seed"])

    groups = df["entity"].to_numpy()
    strata = (df["domain"].astype(str) + "|"
              + df["label"].astype(bool).astype(int).astype(str)).to_numpy()

    sgkf = StratifiedGroupKFold(n_splits=n_folds, shuffle=True,
                                random_state=seed)
    folds: list[dict] = []
    assignment = np.full(len(df), -1, dtype=int)
    for fold, (train_idx, test_idx) in enumerate(
            sgkf.split(df, y=strata, groups=groups)):
        assignment[test_idx] = fold
        folds.append({"fold": fold, "test_ids": [df["id"].iloc[i]
                                                 for i in test_idx]})

    _verify_assignment(df, assignment, n_folds)

    doc = {
        "seed": seed,
        "n_folds": n_folds,
        "group_by": cfg["splits"]["group_by"],
        "stratify_by": cfg["splits"]["stratify_by"],
        "sha256": _assignment_sha256(folds),
        "folds": folds,
    }
    path = folds_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=1, sort_keys=True),
                    encoding="utf-8")
    return doc


def _verify_assignment(df: pd.DataFrame, assignment: np.ndarray,
                       n_folds: int) -> None:
    """Fail-loud self-audit of the partition (called before writing)."""
    if (assignment < 0).any():
        raise RuntimeError("internal error: some statements were not "
                           "assigned to any fold")
    # (1) zero leakage: an entity lives in exactly one test fold
    per_entity = (pd.DataFrame({
        "entity": df["entity"].to_numpy(),
        "fold": assignment,
    }).groupby("entity")["fold"].nunique())
    if (per_entity > 1).any():
        leaked = per_entity[per_entity > 1]
        raise RuntimeError(
            f"entity leakage detected: {len(leaked)} entities appear in "
            "more than one fold (e.g. "
            f"{list(leaked.index[:5])})")
    # (2) every fold holds both classes of every domain with >= 2
    # entities of that (domain, label) stratum
    work = df.assign(fold=assignment)
    stats = (work.groupby(["domain", "label", "fold"])
                 ["entity"].nunique().rename("n_entities").reset_index())
    counts = (work.groupby(["domain", "label"])
                  ["entity"].nunique().rename("n_entities_total")
                  .reset_index())
    merged = stats.merge(counts, on=["domain", "label"])
    fragile = merged[(merged["n_entities_total"] >= 2 * n_folds)
                     & (merged["n_entities"] == 0)]
    if len(fragile):
        raise RuntimeError(
            "fold composition violation: some (domain, label) strata "
            "with enough entities are missing from folds: "
            f"{fragile[['domain', 'label', 'fold']].to_dict('records')[:5]}")


def load_folds(cfg: dict) -> dict:
    """Load folds.json and verify its sha256 integrity."""
    path = folds_path(cfg)
    if not path.is_file():
        raise RuntimeError(
            f"{path} not found: run `make data` "
            "(scripts/prepare_data.py) first")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("sha256") != _assignment_sha256(doc.get("folds", [])):
        raise RuntimeError(
            f"{path}: sha256 mismatch - the fold anchor was modified; "
            "regenerate it with make data and never edit it by hand")
    return doc


def fold_of_map(folds: dict) -> dict[str, int]:
    """statement id -> test fold index."""
    out: dict[str, int] = {}
    for fold in folds["folds"]:
        for sid in fold["test_ids"]:
            if sid in out:
                raise RuntimeError(
                    f"statement {sid} appears in two folds: corrupt "
                    "folds.json")
            out[sid] = fold["fold"]
    return out
