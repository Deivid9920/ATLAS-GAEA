"""task_ladder: carga T1/T2/T3, esquema por tarea y digest de suite.

The ladder contract (anchor 8): counts are exact (50/30/20), every
task carries its own tests, and the suite digest is sha256 over the
canonical JSON of the 100 tasks sorted by id. Once frozen, the suite
is immutable for the experiment (moving target prohibition).
"""

from __future__ import annotations

import json
from pathlib import Path

from gv.canon import canonical, sha256_canonical

TIER_COUNTS = {"t1": 50, "t2": 30, "t3": 20}
TASK_REQUIRED_FIELDS = ("id", "tier", "family", "prompt", "tests",
                        "canonical_solution", "triplets", "seed")


def load_task(path: str | Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "tasks" in data:
        raise ValueError(f"{path}: raw task file, not a task document")
    return data


def validate_task(task: dict) -> None:
    missing = [f for f in TASK_REQUIRED_FIELDS if f not in task]
    if missing:
        raise ValueError(f"task {task.get('id')} missing fields: "
                         f"{missing}")
    if task["tier"] not in TIER_COUNTS:
        raise ValueError(f"task {task['id']}: unknown tier "
                         f"{task['tier']}")
    if not task["tests"].strip():
        raise ValueError(f"task {task['id']}: empty tests")
    if not task["prompt"].strip():
        raise ValueError(f"task {task['id']}: empty prompt")


def load_tier(profiles_dir: str | Path, tier: str) -> list[dict]:
    path = Path(profiles_dir) / "code_qa" / f"tasks_{tier}.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    tasks = doc["tasks"]
    if len(tasks) != TIER_COUNTS[tier]:
        raise ValueError(f"{tier}: expected {TIER_COUNTS[tier]} tasks, "
                         f"got {len(tasks)}")
    for task in tasks:
        validate_task(task)
        if task["tier"] != tier:
            raise ValueError(f"task {task['id']}: tier field mismatch")
    ids = [t["id"] for t in tasks]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{tier}: duplicate task ids")
    return tasks


def load_ladder(profiles_dir: str | Path) -> list[dict]:
    """Load T1+T2+T3 in frozen order; fail-loud on any count drift."""
    tasks: list[dict] = []
    for tier in ("t1", "t2", "t3"):
        tasks.extend(load_tier(profiles_dir, tier))
    if len(tasks) != 100:
        raise ValueError(f"ladder must have 100 tasks, got {len(tasks)}")
    return tasks


def suite_digest(tasks: list[dict]) -> str:
    """sha256 over canonical JSON of tasks sorted by id."""
    ordered = sorted(tasks, key=lambda t: t["id"])
    return sha256_canonical([_slim(t) for t in ordered])


def _slim(task: dict) -> dict:
    return {k: task[k] for k in TASK_REQUIRED_FIELDS}


def suite_manifest(profiles_dir: str | Path) -> dict:
    tasks = load_ladder(profiles_dir)
    by_tier = {}
    for tier in TIER_COUNTS:
        by_tier[tier] = sum(1 for t in tasks if t["tier"] == tier)
    return {"n_total": len(tasks), "counts": by_tier,
            "suite_digest": suite_digest(tasks), "version": 1}
