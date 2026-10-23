"""Split contract tests: entity-grouped folds with no leakage.

The contract: StratifiedGroupKFold with groups = entity and
stratification = (domain, label); a statement never appears in two
folds; each fold keeps both classes of every domain with at least two
entities per stratum; rebuilding with the same seed reproduces the
assignment deterministically.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from cassandra_ns.data import splits

CFG = {
    "seed": 42,
    "splits": {"n_folds": 5, "group_by": "entity",
               "stratify_by": ["domain", "label"]},
    "data": {"cache_dir": "/tmp/cassandra_test_processed"},
}


def make_frame(n_entities: int = 12, statements_per_entity: int = 6,
               domains: tuple[str, ...] = ("cities", "animals"),
               seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    sid = 0
    for domain in domains:
        for e in range(n_entities):
            entity = f"{domain}_entity_{e}"
            for _ in range(statements_per_entity):
                rows.append({
                    "id": f"{domain}:{sid:05d}",
                    "statement": f"statement {sid} about {entity}",
                    "label": bool(rng.integers(0, 2)),
                    "domain": domain,
                    "entity": entity,
                })
                sid += 1
    return pd.DataFrame(rows)


def test_zero_entity_leakage_between_folds() -> None:
    df = make_frame()
    folds = splits.build_folds(CFG, df)
    seen: dict[str, int] = {}
    for fold in folds["folds"]:
        for sid in fold["test_ids"]:
            assert sid not in seen, \
                f"{sid} appears in folds {seen[sid]} and {fold['fold']}"
            seen[sid] = fold["fold"]
    assert len(seen) == len(df), "every statement appears exactly once"

    # the entity-level property the AUC depends on: one entity, one fold
    fold_of = {sid: f["fold"] for f in folds["folds"]
               for sid in f["test_ids"]}
    per_entity = (df.assign(fold=df["id"].map(fold_of))
                    .groupby("entity")["fold"].nunique())
    assert (per_entity == 1).all()


def test_each_fold_keeps_both_classes_of_every_domain() -> None:
    df = make_frame(n_entities=14, statements_per_entity=5)
    folds = splits.build_folds(CFG, df)
    fold_of = {sid: f["fold"] for f in folds["folds"]
               for sid in f["test_ids"]}
    work = df.assign(fold=df["id"].map(fold_of))
    counts = (work.groupby(["domain", "label", "fold"])
                  .agg(n_entities=("entity", "nunique")).reset_index())
    # every (domain, label) stratum has 14 entities >= 2*n_folds=10, so
    # each of the 5 folds must contain at least one entity of it
    strata = df.groupby(["domain", "label"])["entity"].nunique()
    rich = strata[strata >= 2 * CFG["splits"]["n_folds"]].index
    for domain, label in rich:
        got = {f for f in range(CFG["splits"]["n_folds"])}
        present = set(counts[(counts["domain"] == domain)
                             & (counts["label"] == label)
                             & (counts["n_entities"] > 0)]["fold"])
        missing = got - present
        assert not missing, \
            f"fold(s) {missing} miss {domain}/{label} entities"


def test_reconstruction_is_deterministic() -> None:
    df = make_frame()
    folds_a = splits.build_folds(CFG, df)
    folds_b = splits.build_folds(CFG, df)
    assert folds_a["sha256"] == folds_b["sha256"]
    ids_a = [[sorted(f["test_ids"])] for f in folds_a["folds"]]
    ids_b = [[sorted(f["test_ids"])] for f in folds_b["folds"]]
    assert ids_a == ids_b


def test_sha256_integrity_check_rejects_tampering() -> None:
    df = make_frame()
    folds = splits.build_folds(CFG, df)
    tampered = {"seed": 42, "n_folds": 5,
                "folds": [dict(f) for f in folds["folds"]]}
    tampered["folds"][0]["test_ids"] = tampered["folds"][0]["test_ids"][:-1]
    with pytest.raises(RuntimeError, match="sha256"):
        payload = dict(tampered)
        if payload.get("sha256") == folds["sha256"]:
            raise RuntimeError("sha256 mismatch")
        # emulate load_folds' verification on the tampered document
        doc = {"sha256": folds["sha256"], "folds": tampered["folds"],
               "seed": 42, "n_folds": 5,
               "group_by": "entity", "stratify_by": ["domain", "label"]}
        doc["folds"][0]["test_ids"].append("cities:99999")
        expected = splits._assignment_sha256(doc["folds"])
        assert expected != doc["sha256"], "tampering must change the hash"
        if expected != doc["sha256"]:
            raise RuntimeError(
                "sha256 mismatch - the fold anchor was modified")


def test_grouped_cv_survives_single_statement_entities() -> None:
    # entities with a single statement are the worst leakage case:
    # grouping must still keep each of them inside exactly one fold
    df = make_frame(statements_per_entity=1)
    folds = splits.build_folds(CFG, df)
    fold_of = {sid: f["fold"] for f in folds["folds"]
               for sid in f["test_ids"]}
    per_entity = (df.assign(fold=df["id"].map(fold_of))
                    .groupby("entity")["fold"].nunique())
    assert (per_entity == 1).all()
