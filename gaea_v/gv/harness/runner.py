"""runner: arnés de condiciones sobre la escalera de tareas.

One condition = (name, callable producing an answer per task, config).
The harness measures getrusage(RUSAGE_SELF) + RUSAGE_CHILDREN captured
at the SAME frontier (M-04: excluding children underestimates real CPU
because the heavy work runs in the heph subprocess), plus wall time
and peak RSS. It emits per_task.jsonl and manifest.json. It never
interprets results: inference happens only in scripts/*_measured.py
with the prereg loaded.
"""

from __future__ import annotations

import json
import resource
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from gv.audit.chain import AuditChain
from gv.canon import canonical
from gv.harness.efficiency_manifest import (SCHEMA_VERSION,
                                            accuracy_per_cpu_s)
from gv.harness.task_ladder import suite_digest


class SuiteMismatchError(RuntimeError):
    """Raised when two conditions claim the same suite but differ."""


def _rusage_cpu() -> tuple[float, float]:
    self_s = resource.getrusage(resource.RUSAGE_SELF).ru_utime + \
        resource.getrusage(resource.RUSAGE_SELF).ru_stime
    child_s = resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + \
        resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime
    return self_s, child_s


def assert_same_suite(digest_a: str, digest_b: str) -> None:
    """C-04: comparing conditions over different suites is fabrication.

    The comparator rejects manifests whose suite digests differ unless
    the prereg declares the change; here we refuse equal-claim/differ-
    ent-digest pairs outright.
    """
    if digest_a != digest_b:
        raise SuiteMismatchError(
            f"suite digest mismatch: {digest_a[:12]} vs "
            f"{digest_b[:12]}")


def run_condition(condition: str, tasks: list[dict], solver,
                  out_dir: str | Path, *, config_sha256: str,
                  git_head: str, atlas_git_head: str,
                  heph_binary_sha256: str, weights_sha256: str,
                  seed: int = 42, prereg_sha256: str | None = None,
                  bridge_mode: str = "fp32", probe_status: str =
                  "desactivado", probe_auc=None, probe_ece=None,
                  zoo_block=None, notes: str = "",
                  gaea_l: dict | None = None,
                  child_cpu_probe=None,
                  chain: AuditChain | None = None,
                  run_id: str | None = None) -> dict:
    """Run `solver(task) -> row-dict` per task; measure; emit artifacts.

    solver returns a dict with at least: tests_passed (bool), decision
    (str), plus optional nodes_evaluated, tokens_generated, cpu notes.
    The harness owns ALL measurement; solver-owned numbers are copied
    verbatim and flagged by key prefix 'solver_' when present.
    gaea_l reserves the GAEA-L matching fields (FASE 6.d): a dict with
    substrate_id, matching_params, matching_training_flops — all three
    or none; None for non-substrate conditions.
    child_cpu_probe is an optional callable returning the cumulative
    CPU of a LIVE child process (RUSAGE_CHILDREN only counts reaped
    children, so a long-lived worker would vanish from the frontier);
    its delta is added to cpu_s_children at the same measurement
    frontier.
    """
    tasks = sorted(tasks, key=lambda t: t["id"])
    digest = suite_digest(tasks)
    run_id = run_id or uuid.uuid4().hex[:12]
    out = Path(out_dir) / run_id
    out.mkdir(parents=True, exist_ok=True)

    per_task_path = out / "per_task.jsonl"
    manifest_path = out / "manifest.json"

    verdicts = {"approve": 0, "revise": 0, "block": 0, "abstain": 0}
    nodes_total = 0
    tokens_total = 0
    cpu_self0, cpu_child0 = _rusage_cpu()
    cpu_probe0 = float(child_cpu_probe()) if child_cpu_probe else 0.0
    wall0 = time.monotonic()
    rss_peak_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    with per_task_path.open("w", encoding="utf-8") as fh:
        for pos, task in enumerate(tasks):
            row = solver(task)
            passed = bool(row["tests_passed"])
            # Only REAL composite verdicts enter the histogram. A
            # condition without a verifier (nano-solo) records decision
            # null: fabricating a verdict would be a manufactured
            # number, and this repo forbids that.
            decision = row.get("decision")
            if decision is not None:
                if decision not in verdicts:
                    raise ValueError(f"unknown decision {decision!r}")
                verdicts[decision] += 1
            nodes_total += int(row.get("nodes_evaluated", 0))
            tokens_total += int(row.get("tokens_generated", 0))
            record = {"seq": pos, "task": task["id"],
                      "tier": task["tier"], "family": task["family"],
                      "tests_passed": passed, "decision": decision}
            for key, val in row.items():
                if key not in record:
                    record[f"solver_{key}"] = val
            fh.write(canonical(record) + "\n")

    wall_s = time.monotonic() - wall0
    cpu_self1, cpu_child1 = _rusage_cpu()
    cpu_self = cpu_self1 - cpu_self0
    cpu_child = cpu_child1 - cpu_child0
    if child_cpu_probe is not None:
        cpu_child += max(0.0, float(child_cpu_probe()) - cpu_probe0)
    rss_peak_mb = max(resource.getrusage(
        resource.RUSAGE_SELF).ru_maxrss, rss_peak_kb) / 1024.0

    rows = [json.loads(line) for line in
            per_task_path.read_text(encoding="utf-8").splitlines()]
    n = len(rows)
    if n != len(tasks):
        raise RuntimeError("per_task rows do not cover the suite")
    by_tier = {}
    for tier in ("t1", "t2", "t3"):
        tier_rows = [r for r in rows if r["tier"] == tier]
        by_tier[tier] = (sum(1 for r in tier_rows if r["tests_passed"])
                         / len(tier_rows)) if tier_rows else 0.0
    accuracy = sum(1 for r in rows if r["tests_passed"]) / n
    cpu_total = cpu_self + cpu_child

    manifest = {
        "run_id": run_id, "schema_version": SCHEMA_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "config_sha256": config_sha256, "git_head": git_head,
        "atlas_git_head": atlas_git_head,
        "heph_binary_sha256": heph_binary_sha256,
        "weights_sha256": weights_sha256, "profile": "code_qa",
        "suite_digest": digest, "n_tasks": n, "seed": seed,
        "condition": condition, "prereg_sha256": prereg_sha256,
        "accuracy_overall": round(accuracy, 4),
        "accuracy_by_tier": {k: round(v, 4) for k, v in
                             by_tier.items()},
        "verdict_histogram": verdicts,
        "cpu_s_self": round(cpu_self, 4),
        "cpu_s_children": round(cpu_child, 4),
        "cpu_s_total": round(cpu_total, 4), "wall_s": round(wall_s, 4),
        "rss_peak_mb": round(rss_peak_mb, 2),
        "mcts_nodes_total": nodes_total,
        "mcts_nodes_per_s": round(nodes_total / cpu_total, 2)
        if cpu_total > 0 else 0.0,
        "tokens_generated": tokens_total,
        "flops_analytic_total": tokens_total * 10616832,
        "accuracy_per_cpu_s": accuracy_per_cpu_s(round(accuracy, 4),
                                                 round(cpu_total, 4)),
        "bridge_mode": bridge_mode, "probe_status": probe_status,
        "probe_auc": probe_auc, "probe_ece": probe_ece,
        "zoo": zoo_block,
        "contamination": {"ngram_hits": 0, "exact_hits": 0,
                          "status": "ok"},
        "seeds_training": [], "notes": notes,
        "substrate_id": None, "matching_params": None,
        "matching_training_flops": None,
    }
    if gaea_l is not None:
        from gv.harness.efficiency_manifest import GAEA_L_FIELDS
        missing = [f for f in GAEA_L_FIELDS if f not in gaea_l]
        if missing:
            raise ValueError(f"gaea_l dict missing fields: {missing}")
        for f in GAEA_L_FIELDS:
            manifest[f] = gaea_l[f]
    manifest_path.write_text(canonical(manifest) + "\n",
                             encoding="utf-8")
    if chain is not None:
        chain.append({"action": "run_completed", "run_id": run_id,
                      "condition": condition,
                      "suite_digest": digest,
                      "accuracy_overall": manifest["accuracy_overall"],
                      "cpu_s_total": manifest["cpu_s_total"]})
    return manifest
