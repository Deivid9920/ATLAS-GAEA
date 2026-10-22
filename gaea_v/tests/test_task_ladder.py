"""Anchor 8: task ladder contract — tier counts exact (50/30/20),
schema per task, digest stability.

The suite files are frozen in FASE 2; this anchor validates the
loader/validator/digest machinery against a synthetic ladder built in
the temp dir, plus the real suite once frozen (skipped until then via
the file existing check)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gv.harness.task_ladder import (TIER_COUNTS, load_ladder,
                                    suite_digest, validate_task,
                                    suite_manifest)


def _task(idx: int, tier: str) -> dict:
    return {"id": f"{'T2' if tier == 't2' else 'T1'}-{idx:04d}",
            "tier": tier, "family": "sum_list",
            "prompt": f"Write sum_list variant {idx}",
            "tests": "assert sum_list([1]) == 1\n",
            "canonical_solution": "def sum_list(xs):\n"
                                  "    return sum(xs)\n",
            "triplets": [], "seed": 42}


@pytest.fixture
def synthetic_ladder(tmp_path):
    prof = tmp_path / "code_qa"
    prof.mkdir(parents=True)
    t1 = [_task(i, "t1") for i in range(50)]
    t2 = [_task(1000 + i, "t2") for i in range(30)]
    t3 = [_task(2000 + i, "t3") for i in range(20)]
    (prof / "tasks_t1.json").write_text(json.dumps({"tasks": t1}))
    (prof / "tasks_t2.json").write_text(json.dumps({"tasks": t2}))
    (prof / "tasks_t3.json").write_text(json.dumps({"tasks": t3}))
    return tmp_path, {"t1": t1, "t2": t2, "t3": t3}


def test_tier_counts_frozen():
    assert TIER_COUNTS == {"t1": 50, "t2": 30, "t3": 20}


def test_load_ladder_counts(synthetic_ladder):
    tmp_path, _ = synthetic_ladder
    tasks = load_ladder(tmp_path)
    assert len(tasks) == 100
    tiers = {"t1": 0, "t2": 0, "t3": 0}
    for task in tasks:
        tiers[task["tier"]] += 1
    assert tiers == TIER_COUNTS


def test_suite_digest_stable_and_order_free(synthetic_ladder):
    tmp_path, tiers = synthetic_ladder
    all_tasks = tiers["t1"] + tiers["t2"] + tiers["t3"]
    d1 = suite_digest(all_tasks)
    d2 = suite_digest(list(reversed(all_tasks)))
    assert d1 == d2
    assert len(d1) == 64
    mutated = [dict(all_tasks[0], prompt="changed")] + all_tasks[1:]
    assert suite_digest(mutated) != d1


def test_validate_task_rejects_missing_fields():
    task = _task(1, "t2")
    for field in ("id", "tier", "family", "prompt", "tests",
                  "canonical_solution", "triplets", "seed"):
        broken = dict(task)
        del broken[field]
        with pytest.raises(ValueError):
            validate_task(broken)
    with pytest.raises(ValueError):
        validate_task(dict(task, tier="t9"))


def test_count_drift_fails_loud(synthetic_ladder):
    tmp_path, _ = synthetic_ladder
    path = tmp_path / "code_qa" / "tasks_t2.json"
    doc = json.loads(path.read_text())
    doc["tasks"] = doc["tasks"][:-1]
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError):
        load_ladder(tmp_path)


def test_real_suite_frozen_present():
    profiles = Path(__file__).resolve().parents[1] / "profiles"
    manifest_path = profiles / "code_qa" / "suite_manifest.json"
    if not manifest_path.exists():
        pytest.skip("suite not frozen yet (FASE 2)")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["n_total"] == 100
    assert manifest["counts"] == TIER_COUNTS
    live = suite_manifest(profiles)
    assert live["suite_digest"] == manifest["suite_digest"], \
        "frozen suite digest drifted from the live recomputation"
