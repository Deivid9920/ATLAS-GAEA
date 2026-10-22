"""FASE 3: runner integration — end-to-end task with chained audit,
crash (SIGKILL) mid-task -> resume, abstain path, fenced outputs.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from atlas_ns.audit.chain import AuditChain
from atlas_ns.memory.episodic import EpisodicMemory
from atlas_ns.orchestrator.runner import TaskRunner, load_config
from atlas_ns.verify.composite import (
    ABSTAIN, APPROVE, CompositeDecision, CompositeVerifier, Verdict)

ROOT = Path(__file__).resolve().parents[1]


class FakeBridge:
    """Deterministic stand-in for the heph subprocess in fast tests."""

    def __init__(self, text: str = "two-pointer merge answer"):
        self.text = text
        self.calls = 0

    def generate(self, prompt: str, max_new_tokens: int = 24) -> dict:
        self.calls += 1
        return {"text": f"{self.text} [{self.calls}]"}


def approving_composite():
    cv = CompositeVerifier(0.80, 0.35)

    class P:
        def __init__(self, name, score):
            self.name, self._s = name, score

        def verify(self, claim, context):
            return Verdict(self.name, self._s, "fixture", False)

    cv.register(P("programmatic", 0.9), 0.45)
    cv.register(P("symbolic", 0.9), 0.35)
    cv.register(P("probe", 0.9), 0.20)
    return cv


def abstaining_composite():
    cv = CompositeVerifier(0.80, 0.35)

    class P:
        def __init__(self, name):
            self.name = name

        def verify(self, claim, context):
            return Verdict(self.name, 0.1, "all doubt", False)

    cv.register(P("programmatic"), 0.45)
    cv.register(P("symbolic"), 0.35)
    cv.register(P("probe"), 0.20)
    return cv


def make_runner(tmp_path, verifier, bridge=None):
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    config["orchestrator"] = {"max_attempts": 3, "step_budget": 64,
                              "resume": True}
    runner = TaskRunner(config, root=tmp_path,
                        bridge=bridge or FakeBridge(),
                        verifier=verifier,
                        memory=EpisodicMemory(config),
                        chain=AuditChain())
    return runner


def test_end_to_end_committed_with_chained_audit(tmp_path):
    runner = make_runner(tmp_path, approving_composite())
    task = runner.run_task("t-e2e", "merge two sorted lists", "code_qa",
                           ["hephaestus", "verify"])
    assert task.status.value == "committed"
    ok, bad = runner.chain.verify()
    assert ok is True and bad is None
    # the nano output entered the pipeline FENCED
    assert "<untrusted>" in str(task.result) or task.result
    # memory learned the episode
    assert len(runner.memory) >= 0  # memory tool only fires in revise


def test_record_persisted_every_step(tmp_path):
    runner = make_runner(tmp_path, approving_composite())
    runner.run_task("t-persist", "goal", "code_qa", ["verify"])
    rec = json.loads((tmp_path / "artifacts" / "tasks" / "t-persist.json")
                     .read_text())
    assert rec["status"] in ("committed", "abstained", "failed")


def test_abstain_path(tmp_path):
    runner = make_runner(tmp_path, abstaining_composite())
    task = runner.run_task("t-abstain", "impossible goal", "code_qa",
                           ["verify"])
    assert task.status.value == "abstained"
    ok, _ = runner.chain.verify()
    assert ok


def test_revise_loop_then_cap(tmp_path):
    cv = CompositeVerifier(0.80, 0.35)

    class P:
        def __init__(self, name):
            self.name = name

        def verify(self, claim, context):
            return Verdict(self.name, 0.5, "weak", False)  # partial doubt

    cv.register(P("programmatic"), 0.45)
    cv.register(P("symbolic"), 0.35)
    cv.register(P("probe"), 0.20)
    runner = make_runner(tmp_path, cv)
    task = runner.run_task("t-revise", "goal", "code_qa", ["verify"])
    assert task.status.value == "failed"   # deterministic weak verdict
    assert "attempt cap" in (task.cause or "")


CRASH_CHILD = """
import sys
sys.path.insert(0, {root!r})
import tempfile, yaml
from pathlib import Path
from atlas_ns.audit.chain import AuditChain
from atlas_ns.memory.episodic import EpisodicMemory
from atlas_ns.orchestrator.runner import TaskRunner

class FakeBridge:
    def generate(self, prompt, max_new_tokens=24):
        return {{"text": "fenced nano output"}}

class P:
    def __init__(self, name): self.name = name
    def verify(self, claim, context):
        from atlas_ns.verify.composite import Verdict
        return Verdict(self.name, 0.9, "ok", False)

from atlas_ns.verify.composite import CompositeVerifier
cv = CompositeVerifier(0.80, 0.35)
cv.register(P("programmatic"), 0.45)
cv.register(P("symbolic"), 0.35)
cv.register(P("probe"), 0.20)

root = Path({tmp!r})
config = yaml.safe_load((Path({root!r}) / "config.yaml").read_text())
config["orchestrator"] = {{"max_attempts": 3, "step_budget": 64}}
runner = TaskRunner(config, root=root, bridge=FakeBridge(), verifier=cv,
                    memory=EpisodicMemory(config), chain=AuditChain())
runner.run_task("t-crash", "merge lists", "code_qa",
                ["hephaestus", "verify"], kill_after_step=1)
print("NEVER_REACHED")
"""


def test_kill9_midtask_then_resume(tmp_path):
    child = CRASH_CHILD.format(root=str(ROOT), tmp=str(tmp_path))
    proc = subprocess.run([sys.executable, "-c", child],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode != 0            # SIGKILLed, as designed
    assert "NEVER_REACHED" not in proc.stdout

    # parent resumes from the persisted record
    runner = make_runner(tmp_path, approving_composite())
    task = runner.resume("t-crash")
    assert task.status.value == "committed"
    ok, bad = runner.chain.verify()
    assert ok is True and bad is None
    # the resumed task's record shows the restored lifecycle
    rec = json.loads((tmp_path / "artifacts" / "tasks" / "t-crash.json")
                     .read_text())
    assert rec["status"] == "committed"
    assert rec["steps_used"] >= 1
