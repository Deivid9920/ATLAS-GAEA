"""Orchestrator runner (FASE 3): materializes the machine ANCLA.

The runner executes the actions machine.step() returns, calls tools
under permissions, feeds every event to the tamper-evident audit chain,
persists a TaskRecord after EVERY step (crash-resumable, #17) and
fences every tool output before it can influence anything.

Tool dispatch (fail-closed permissions):
  hephaestus : bridge.generate (perm: execute)
  verify     : composite verifier (perm: readonly)
  memory     : episodic memory add/retrieve (perm: write)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import yaml

from atlas_ns.audit.chain import AuditChain
from atlas_ns.bridge.hephaestus import HephaestusBridge
from atlas_ns.memory.episodic import EpisodicMemory
from atlas_ns.orchestrator.machine import Action, Status, Task, step
from atlas_ns.safety.fencing import fence
from atlas_ns.safety.permissions import PermissionTable, from_config


def _inputs_hash(*parts) -> str:
    import hashlib

    return hashlib.sha256(json.dumps(
        [str(p) for p in parts], sort_keys=True).encode()).hexdigest()[:16]


class TaskRunner:
    def __init__(self, config: dict, root: Path | None = None,
                 bridge: HephaestusBridge | None = None,
                 verifier: Callable | None = None,
                 memory: EpisodicMemory | None = None,
                 chain: AuditChain | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2]
        self.config = config
        # config grants govern EXTERNAL tools; the runner adds its own
        # INTERNAL tool grants (verify/memory) — fail-closed still holds
        # for anything unlisted.
        self.permissions: PermissionTable = from_config(config)
        self.permissions.grant("verify", "readonly")
        self.permissions.grant("memory", "write")
        self.bridge = bridge or HephaestusBridge(config, repo_root=self.root)
        if verifier is None:
            self.verify_fn = _no_verifier
        elif hasattr(verifier, "evaluate"):  # a CompositeVerifier ANCLA
            self.verify_fn = lambda claim, context=None: verifier.evaluate(
                claim, context)
        else:
            self.verify_fn = verifier
        self.memory = memory or EpisodicMemory(config)
        self.chain = chain or AuditChain()
        orch = config.get("orchestrator", {})
        self.max_attempts = int(orch.get("max_attempts", 3))
        self.step_budget = int(orch.get("step_budget", 64))
        self.records_dir = self.root / "artifacts" / "tasks"
        self.records_dir.mkdir(parents=True, exist_ok=True)

    # -- task record persistence (#17) --------------------------------------
    def _record_path(self, task_id: str) -> Path:
        return self.records_dir / f"{task_id}.json"

    def persist(self, task: Task) -> None:
        self._record_path(task.task_id).write_text(
            json.dumps(task.to_record(), ensure_ascii=False, indent=1),
            encoding="utf-8")

    def load_task(self, task_id: str) -> Task:
        rec = json.loads(self._record_path(task_id)
                         .read_text(encoding="utf-8"))
        return Task.from_record(rec)

    # -- tool dispatch --------------------------------------------------------
    def _dispatch(self, task: Task, action: Action) -> str:
        """Execute one action; returns fenced tool output."""
        if action.kind != "call_tool":
            return ""
        tool = action.tool or ""
        args = dict(action.args or {})
        perm = {"hephaestus": "execute", "verify": "readonly",
                "memory": "write"}.get(tool)
        if perm is None:  # fail-closed: unlisted tool
            raise PermissionError(
                f"tool {tool!r} not in the permission table")
        event = self.permissions.require(tool, perm)
        self.chain.append({**event, "task": task.task_id})

        if tool == "hephaestus":
            prompt = args.get("prompt", task.goal)
            res = self.bridge.generate(prompt, max_new_tokens=24)
            return fence(res["text"])
        if tool == "verify":
            decision = self.verify_fn(args.get("previous", "") or task.result,
                                      args.get("context"))
            self.chain.append({
                "action": "verifier_decision", "task": task.task_id,
                "inputs_hash": _inputs_hash(args.get("previous", "")),
                "verdict": decision.decision,
                "causes": list(decision.causes)[:4]})
            # stash the decision for _advance; the machine is ACTING so
            # the event NOW must be a plain tool_result
            self._pending_decision = decision
            return f"verdict:{decision.decision}"
        if tool == "memory":
            self.memory.add(task.task_id, task.goal,
                            list(task.plan), args.get("previous", ""),
                            args.get("feedback", ""))
            self.chain.append({"action": "memory_write",
                               "task": task.task_id})
            return "memory:ok"
        raise PermissionError(f"no dispatch for tool {tool!r}")

    # -- main loop ---------------------------------------------------------------
    def run_task(self, task_id: str, goal: str, profile: str,
                 plan: list[str], kill_after_step: int | None = None) -> Task:
        """Drive one task to a terminal status through machine.step()."""
        task = Task(task_id=task_id, goal=goal, profile=profile,
                    max_attempts=self.max_attempts,
                    step_budget=self.step_budget)
        self.persist(task)
        self.chain.append({"action": "task_received", "task": task_id,
                           "inputs_hash": _inputs_hash(goal, plan)})
        event: dict = {"kind": "plan_ready", "plan": plan}
        steps = 0
        while True:
            task, action = step(task, event)
            self.persist(task)
            self.chain.append({"action": f"step_{action.kind}",
                               "task": task_id, "tool": action.tool,
                               "status": task.status.value,
                               "steps_used": task.steps_used,
                               "attempts": task.attempts})

            if kill_after_step is not None and steps >= kill_after_step:
                # crash-test hook (#17): hard-kill THIS process mid-task
                import os
                import signal

                self.chain.append({"action": "crash_test_kill",
                                   "task": task_id})
                self.persist(task)
                os.kill(os.getpid(), signal.SIGKILL)

            if action.kind == "wait":
                if task.status in (Status.COMMITTED, Status.ABSTAINED,
                                   Status.FAILED, Status.BUDGET_EXHAUSTED):
                    return task  # terminal by budget/wait: done
                if task.status == Status.VERIFYING:
                    event = self._advance(task, action)
                    steps += 1
                    continue
                # ACTING wait only comes from crash_recover: needs a
                # tool_result replay
                event = {"kind": "tool_result",
                         "output": task.result or ""}
                steps += 1
                continue
            if action.kind == "emit":
                self.chain.append({"action": "task_emitted",
                                   "task": task_id,
                                   "verdict": "committed",
                                   "inputs_hash": _inputs_hash(
                                       task.result)})
                return task
            if action.kind == "fail":
                self.chain.append({"action": "task_failed",
                                   "task": task_id,
                                   "cause": task.cause})
                return task
            if action.kind == "abstain":
                self.chain.append({"action": "task_abstained",
                                   "task": task_id,
                                   "cause": task.cause})
                return task
            if action.kind == "call_tool":
                output = self._dispatch(task, action)
                self.chain.append({"action": "tool_result",
                                   "task": task_id, "tool": action.tool,
                                   "inputs_hash": _inputs_hash(output[:64]),
                                   "verdict": None})
                event = {"kind": "tool_result", "output": output}
                steps += 1
                continue
            raise RuntimeError(f"unhandled action {action.kind}")

    # -- event wiring ----------------------------------------------------------
    def _advance(self, task: Task, action: Action) -> dict:
        """After a VERIFYING wait, produce the decision event: reuse the
        verifier's decision when 'verify' just ran, else evaluate the
        task result fresh through the composite."""
        decision = getattr(self, "_pending_decision", None)
        self._pending_decision = None
        if decision is None:
            decision = self.verify_fn(task.result or "", None)
        self.chain.append({
            "action": "verifier_decision", "task": task.task_id,
            "inputs_hash": _inputs_hash(task.result or ""),
            "verdict": decision.decision,
            "causes": list(decision.causes)[:4]})
        return {"kind": "decision", "decision": decision.decision,
                "reason": "; ".join(decision.causes[:2])}

    # -- crash recovery (#17) ---------------------------------------------------
    def resume(self, task_id: str) -> Task:
        """CRASH_RECOVER: restore the persisted record and continue."""
        task = self.load_task(task_id)
        self.chain.append({"action": "crash_recover", "task": task_id,
                           "restored_status": task.status.value})
        if task.status in (Status.COMMITTED, Status.ABSTAINED,
                           Status.FAILED, Status.BUDGET_EXHAUSTED):
            return task  # terminal already: nothing to redo
        if task.status == Status.RECEIVED:
            return self.run_task(task.task_id, task.goal, task.profile,
                                 list(task.plan) or ["verify"])
        event = {"kind": "crash_recover"}
        while True:
            task, action = step(task, event)
            self.persist(task)
            if action.kind == "wait":
                if task.status == Status.VERIFYING:
                    event = self._advance(task, action)
                else:
                    event = {"kind": "tool_result",
                             "output": task.result or ""}
            elif action.kind == "call_tool":
                output = self._dispatch(task, action)
                event = {"kind": "tool_result", "output": output}
            elif action.kind in ("emit", "fail", "abstain"):
                self.chain.append({"action": f"resumed_{action.kind}",
                                   "task": task_id})
                return task
            else:
                raise RuntimeError(f"resume: unhandled {action.kind}")


def _no_verifier(claim: str, context: dict | None):
    """FASE 3 default: honest ABSTAIN if no composite was wired."""
    from atlas_ns.verify.composite import CompositeDecision

    return CompositeDecision(
        "abstain", 0.0, (),
        ("no composite verifier wired: honest abstention",))


def load_config(path: str | Path = "config.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
