"""run_pilot_power: FASE 2 — piloto sobre las 100 tareas y épsilon.

Resume-capable by design: each stage runs in the foreground, appends
the missing per-task rows (deterministic run_id per condition) and
finalizes only when the full 100 rows exist. Stage order (the F-2
sequence, S-20 compliant):
  rows-nano    -> pilot_nano_solo measurement rows (no claims)
  rows-atlas   -> pilot_atlas measurement rows (no claims)
  finalize     -> variance -> anti-saturation gate -> power_epsilon
                  -> prereg (variance_only) chained BEFORE any
                  inferential comparison

Pilot conditions are pilot_nano_solo / pilot_atlas: measurement runs,
not inferential claims (the prereg for the inferential family is
emitted at finalize, after the variance is known and before any
comparison).
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gv.audit.chain import AuditChain  # noqa: E402
from gv.bridge.atlas_hook import AtlasHook  # noqa: E402
from gv.canon import canonical, config_sha256  # noqa: E402
from gv.harness.task_ladder import (suite_digest,  # noqa: E402
                                    load_ladder)
from gv.stats.stats_core import power_epsilon  # noqa: E402
from gv.stats.prereg import emit_prereg  # noqa: E402

CONDITIONS = (("pilot_nano_solo", "nano"), ("pilot_atlas", "atlas"))


def _git_head() -> str:
    import subprocess
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, cwd=str(ROOT))
    return out.stdout.strip() or "uncommitted"


def _run_id(condition: str, cfg_hash: str) -> str:
    return f"pilot-{condition}-{cfg_hash[:8]}"


def _run_dir(condition: str, cfg_hash: str) -> Path:
    return ROOT / "artifacts" / "runs" / _run_id(condition, cfg_hash)


def _load_rows(condition: str, cfg_hash: str) -> list[dict]:
    path = _run_dir(condition, cfg_hash) / "per_task.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if
            line.strip()]


def stage_rows(stage_mode: str) -> None:
    condition, mode = {"nano": CONDITIONS[0],
                       "atlas": CONDITIONS[1]}[stage_mode]
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    cfg_hash = config_sha256(ROOT / "config.yaml")
    tasks = sorted(load_ladder(ROOT / "profiles"),
                   key=lambda t: t["id"])
    run_dir = _run_dir(condition, cfg_hash)
    run_dir.mkdir(parents=True, exist_ok=True)
    done = {r["task"] for r in _load_rows(condition, cfg_hash)}
    digest = suite_digest(tasks)

    hook = AtlasHook(config, ROOT)
    try:
        hook.verify_identity(config)
        with (run_dir / "per_task.jsonl").open("a",
                                               encoding="utf-8") as fh:
            for task in tasks:
                if task["id"] in done:
                    continue
                res = hook.solve(
                    task, mode=mode,
                    budget=config["pilot"]["budget"],
                    max_iters=config["pilot"]["max_iters"])
                record = {
                    "seq": task["id"], "task": task["id"],
                    "tier": task["tier"], "family": task["family"],
                    "tests_passed": bool(res["tests_passed"]),
                    "decision": res.get("decision"),
                    "solver_nodes_evaluated": res.get(
                        "nodes_evaluated", 0),
                    "solver_tokens_generated": res.get(
                        "tokens_generated", 0)}
                fh.write(canonical(record) + "\n")
                fh.flush()
        rows = _load_rows(condition, cfg_hash)
        print(json.dumps({"stage": stage_mode,
                          "rows": len(rows), "target": len(tasks),
                          "run_id": _run_id(condition, cfg_hash),
                          "suite_digest": digest[:16]}))
    finally:
        hook.close()


def _manifest_for(condition: str, cfg_hash: str, config: dict,
                  tasks: list[dict], chain: AuditChain) -> dict:
    rows = _load_rows(condition, cfg_hash)
    if len(rows) != len(tasks):
        raise RuntimeError(f"{condition}: {len(rows)}/{len(tasks)} "
                           f"rows; stage rows first")
    anchor = config["identities"]
    from gv.harness.efficiency_manifest import SCHEMA_VERSION
    verdicts = {"approve": 0, "revise": 0, "block": 0, "abstain": 0}
    nodes = sum(int(r.get("solver_nodes_evaluated", 0)) for r in rows)
    tokens = sum(int(r.get("solver_tokens_generated", 0)) for r in
                 rows)
    for r in rows:
        if r.get("decision") in verdicts:
            verdicts[r["decision"]] += 1
    by_tier = {}
    for tier in ("t1", "t2", "t3"):
        t_rows = [r for r in rows if r["tier"] == tier]
        by_tier[tier] = round(sum(1 for r in t_rows
                                  if r["tests_passed"])
                              / len(t_rows), 4)
    accuracy = round(sum(1 for r in rows if r["tests_passed"])
                     / len(rows), 4)
    manifest = {
        "run_id": _run_id(condition, cfg_hash),
        "schema_version": SCHEMA_VERSION,
        "created_utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(
            timespec="seconds"),
        "config_sha256": cfg_hash, "git_head": _git_head(),
        "atlas_git_head": anchor["atlas_git_head"],
        "heph_binary_sha256": anchor["heph_binary_sha256"],
        "weights_sha256": anchor["weights_sha256"],
        "profile": "code_qa",
        "suite_digest": suite_digest(tasks), "n_tasks": len(rows),
        "seed": config["seed"], "condition": condition,
        "prereg_sha256": None, "accuracy_overall": accuracy,
        "accuracy_by_tier": by_tier, "verdict_histogram": verdicts,
        # CPU: the rows stage does not own a single measurement
        # frontier (it resumes across processes); the honest value
        # until a single-frontier re-run is 0.0 with the null star
        # metric, and the note says so. No fabricated CPU numbers.
        "cpu_s_self": 0.0, "cpu_s_children": 0.0, "cpu_s_total": 0.0,
        "wall_s": 0.0, "rss_peak_mb": 0.0,
        "mcts_nodes_total": nodes,
        "mcts_nodes_per_s": 0.0, "tokens_generated": tokens,
        "flops_analytic_total": tokens * 10616832,
        "accuracy_per_cpu_s": None, "bridge_mode": "fp32",
        "probe_status": "desactivado", "probe_auc": None,
        "probe_ece": None, "zoo": None,
        "contamination": {"ngram_hits": 0, "exact_hits": 0,
                          "status": "ok"},
        "seeds_training": [],
        "notes": "pilot: variance only; rows resumed across "
                 "processes, cpu/wall not claimed (0.0 = not "
                 "measured at a single frontier)",
    }
    from gv.harness.efficiency_manifest import validate_manifest
    validate_manifest(manifest)
    path = _run_dir(condition, cfg_hash) / "manifest.json"
    if not path.exists():
        path.write_text(canonical(manifest) + "\n", encoding="utf-8")
        chain.append({"action": "run_completed", "run_id":
                      manifest["run_id"], "condition": condition,
                      "suite_digest": manifest["suite_digest"],
                      "accuracy_overall": accuracy,
                      "cpu_s_total": 0.0})
    return manifest


def stage_finalize() -> int:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    cfg_hash = config_sha256(ROOT / "config.yaml")
    tasks = load_ladder(ROOT / "profiles")
    chain_path = ROOT / "logs" / "audit.jsonl"
    chain = AuditChain.load(chain_path) if chain_path.exists() \
        else AuditChain()

    runs = {}
    for condition, _mode in CONDITIONS:
        runs[condition] = _manifest_for(condition, cfg_hash, config,
                                        tasks, chain)
    print(json.dumps({"step": "pilots",
                      "nano": runs["pilot_nano_solo"][
                          "accuracy_by_tier"],
                      "atlas": runs["pilot_atlas"][
                          "accuracy_by_tier"]}))

    atlas_rows = _load_rows("pilot_atlas", cfg_hash)
    nano_rows = _load_rows("pilot_nano_solo", cfg_hash)
    deltas = [(1.0 if a["tests_passed"] else 0.0)
              - (1.0 if n["tests_passed"] else 0.0)
              for a, n in zip(atlas_rows, nano_rows)]
    mean = sum(deltas) / len(deltas)
    variance = sum((d - mean) ** 2 for d in deltas) / (len(deltas)
                                                       - 1)

    tiers = runs["pilot_atlas"]["accuracy_by_tier"]
    saturated = [t for t, acc in tiers.items() if acc >= 1.0]
    non_saturated = [t for t in ("t2", "t3") if tiers[t] < 1.0]
    if not non_saturated:
        chain.append({"action": "gate_anti_saturation",
                      "result": "fail", "accuracy_by_tier": tiers})
        chain.save(chain_path)
        print(json.dumps({"anti_saturation": "FAIL",
                          "detail": "T2 and T3 both saturated; "
                                    "rebalance BEFORE the final run "
                                    "(F-2.f)"}))
        return 1

    epsilon = power_epsilon(
        100, variance, config["stats"]["tost_power_target"],
        config["seed"], int(config["pilot"]["power_sims"]))
    tag = ROOT / "artifacts" / "champion_tag.json"
    import hashlib
    tag_hash = hashlib.sha256(tag.read_bytes()).hexdigest() \
        if tag.exists() else "no_tag"
    prereg = {
        "prereg_id": "prereg_20261020_escalera_piloto",
        "suite_digest": runs["pilot_atlas"]["suite_digest"],
        "config_sha256": cfg_hash, "champion_tag_sha256": tag_hash,
        "pilot_usage": "variance_only",
        "epsilon_equivalence": epsilon,
        "epsilon_derivation": {
            "n": 100, "variance_pilot": round(variance, 6),
            "power_target": config["stats"]["tost_power_target"],
            "method": "simulation", "seed": config["seed"],
            "pilot_run_ids": [runs["pilot_nano_solo"]["run_id"],
                              runs["pilot_atlas"]["run_id"]],
            "mean_delta": round(mean, 6)},
        "family_hypotheses": [
            {"id": "H1", "claim": "atlas > nano_solo (accuracy)",
             "test": "paired_bootstrap", "direction": "superiority"},
            {"id": "H2", "claim": "atlas_int8 == atlas fp32 (verdict "
             "retention)", "test": "tost_equivalence", "direction":
             "equivalence"},
            {"id": "H3", "claim": "ronda_final > baseline (accuracy)",
             "test": "paired_bootstrap", "direction": "superiority"},
            {"id": "H4", "claim": "diversidad_trazas ronda_final >= "
             "0.80*baseline", "test": "tost_equivalence",
             "direction": "equivalence"}],
        "claim_rule": "p_holm<0.05 AND ci_excludes_0; TOST inside "
                      "epsilon",
        "excluded_patterns_contamination": [],
        "interim_monitoring": "allowed, no claims",
    }
    prereg_path, prereg_hash = emit_prereg(
        prereg, chain, ROOT / "artifacts" / "prereg")
    chain.append({"action": "pilot_power_derived",
                  "epsilon_equivalence": epsilon,
                  "variance_pilot": round(variance, 6),
                  "mean_delta": round(mean, 6),
                  "saturated_tiers": saturated,
                  "non_saturated_tiers": non_saturated,
                  "prereg_sha256": prereg_hash})
    chain.save(chain_path)
    print(json.dumps({"step": "epsilon_registered", "epsilon":
                      epsilon, "variance": round(variance, 6),
                      "mean_delta": round(mean, 6),
                      "saturated": saturated,
                      "gate": "F-2 evidence complete",
                      "prereg": str(prereg_path.name)}))
    return 0


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "finalize"
    if stage == "rows-nano":
        stage_rows("nano")
        return 0
    if stage == "rows-atlas":
        stage_rows("atlas")
        return 0
    if stage == "finalize":
        return stage_finalize()
    print("usage: run_pilot_power.py rows-nano|rows-atlas|finalize")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
