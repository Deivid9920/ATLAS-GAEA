#!/usr/bin/env python3
"""CLI: --config --profile --task --budget [--with-crash-test].

Runs one task through the orchestrator (bridge + composite verifier +
episodic memory + audit chain). --with-crash-test executes the task in
a CHILD process that SIGKILLs itself mid-task and then resumes it from
the persisted TaskRecord (#17) — the crash-safety demo.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from atlas_ns.audit.chain import AuditChain
from atlas_ns.bridge.hephaestus import HephaestusBridge
from atlas_ns.memory.episodic import EpisodicMemory
from atlas_ns.orchestrator.runner import TaskRunner
from atlas_ns.verify.composite import CompositeVerifier
from atlas_ns.verify.plugins.policy import PolicyVerifier
from atlas_ns.verify.plugins.probe import ProbeVerifier
from atlas_ns.verify.plugins.programmatic import ProgrammaticVerifier
from atlas_ns.verify.plugins.symbolic import SymbolicVerifier


def build_composite(config: dict, root: Path) -> CompositeVerifier:
    cv = CompositeVerifier(
        tau_approve=config["verifier"]["tau_approve"],
        tau_doubt=config["verifier"]["tau_doubt"])
    cv.register(ProgrammaticVerifier(config),
                config["verifier"]["plugins"]["programmatic"])
    graph_path = root / "profiles" / config["profiles"]["active"] / "graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8")) \
        if graph_path.is_file() else None
    cv.register(SymbolicVerifier(graph),
                config["verifier"]["plugins"]["symbolic"])
    cv.register(ProbeVerifier(config, repo_root=root),
                config["verifier"]["plugins"]["probe"])
    # Hard-block vote (S-08); weight 0.0 keeps the weighted arithmetic
    # of the other verifiers untouched on clean candidates.
    cv.register(PolicyVerifier(config), 0.0)
    return cv


CRASH_CHILD = """
import sys
sys.path.insert(0, {root!r})
from atlas_ns.audit.chain import AuditChain
from atlas_ns.bridge.hephaestus import HephaestusBridge
from atlas_ns.memory.episodic import EpisodicMemory
from atlas_ns.orchestrator.runner import TaskRunner
from run_task_helper import build_composite
import yaml
from pathlib import Path

root = Path({root!r})
config = yaml.safe_load((root / "config.yaml").read_text())
runner = TaskRunner(config, root=root,
                    bridge=HephaestusBridge(config, repo_root=root),
                    verifier=build_composite(config, root),
                    memory=EpisodicMemory(config), chain=AuditChain())
runner.run_task({task_id!r}, {task!r}, {profile!r},
                ["hephaestus", "verify"], kill_after_step=1)
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--profile", default=None)
    ap.add_argument("--task", required=True)
    ap.add_argument("--budget", default="standard")
    ap.add_argument("--with-crash-test", action="store_true")
    ap.add_argument("--task-id", default=None)
    args = ap.parse_args()

    root = Path(args.config).resolve().parent
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    profile = args.profile or config["profiles"]["active"]
    task_id = args.task_id or f"cli_{abs(hash(args.task)) % 100000}"

    if args.with_crash_test:
        # phase 1: the child starts the task and SIGKILLs itself
        helper = root / "scripts" / "run_task_helper.py"
        child = CRASH_CHILD.format(root=str(root), task=args.task,
                                   profile=profile, task_id=task_id)
        proc = subprocess.run([sys.executable, "-c", child],
                              capture_output=True, text=True, timeout=300,
                              cwd=str(helper.parent))
        print(f"crash-test: child exit {proc.returncode} (SIGKILL "
              f"expected: {proc.returncode == -9})")

    runner = TaskRunner(
        config, root=root,
        bridge=HephaestusBridge(config, repo_root=root),
        verifier=build_composite(config, root),
        memory=EpisodicMemory(config), chain=AuditChain())
    task = runner.resume(task_id) if args.with_crash_test else \
        runner.run_task(task_id, args.task, profile,
                        ["hephaestus", "verify"])
    chain_path = root / "logs" / "audit.jsonl"
    runner.chain.save(chain_path)
    print(json.dumps({
        "task": task.task_id, "status": task.status.value,
        "cause": task.cause, "attempts": task.attempts,
        "steps_used": task.steps_used,
        "audit_chain": runner.chain.verify(),
        "audit_log": str(chain_path)}, ensure_ascii=False, indent=1))
    return 0 if task.status.value in ("committed", "abstained") else 1


if __name__ == "__main__":
    raise SystemExit(main())
