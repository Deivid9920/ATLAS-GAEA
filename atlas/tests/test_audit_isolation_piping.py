"""Lote 2 (v1.1.0, ANCHOR_CHANGES #15): el evento `verifier_decision` de la
cadena de auditoría lleva el perfil de aislamiento REAL del sandbox cuando
el verificador lo expone — y NUNCA inventa el campo si no hay dato."""
from pathlib import Path

import yaml

from atlas_ns.audit.chain import AuditChain
from atlas_ns.memory.episodic import EpisodicMemory
from atlas_ns.orchestrator.runner import TaskRunner
from atlas_ns.verify.composite import CompositeVerifier, Verdict

ROOT = Path(__file__).resolve().parents[1]


class FakeBridge:
    def generate(self, prompt, max_new_tokens=24):
        return {"text": "ok"}


class P:
    def __init__(self, name, score):
        self.name, self._s = name, score

    def verify(self, claim, context):
        return Verdict(self.name, self._s, "fixture", False)


def composite_with_last_sandbox(ls):
    cv = CompositeVerifier(0.80, 0.35)
    prog = P("programmatic", 0.9)
    prog.last_sandbox = ls          # lo que run_in_sandbox dejaría puesto
    cv.register(prog, 0.45)
    cv.register(P("symbolic", 0.9), 0.35)
    cv.register(P("probe", 0.9), 0.20)
    return cv


def build_runner(tmp_path, verifier):
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    config["orchestrator"] = {"max_attempts": 3, "step_budget": 64}
    return TaskRunner(config, root=tmp_path, bridge=FakeBridge(),
                      verifier=verifier, memory=EpisodicMemory(config),
                      chain=AuditChain())


def _verifier_decision_events(runner):
    # cada entrada de la cadena envuelve el evento bajo "event" (hash chain)
    return [e["event"] for e in runner.chain.entries
            if e.get("event", {}).get("action") == "verifier_decision"]


def test_verifier_decision_event_carries_sandbox_isolation(tmp_path):
    ls = {"isolation_profile": "subprocess+rlimits",
          "no_network_requested": True, "no_network_enforced": False}
    runner = build_runner(tmp_path, composite_with_last_sandbox(ls))
    runner.run_task("t-iso", "merge lists", "code_qa",
                    ["hephaestus", "verify"])
    events = _verifier_decision_events(runner)
    assert events, "no hubo evento verifier_decision en la cadena"
    assert all(e["sandbox_isolation"] == ls for e in events)


def test_without_last_sandbox_the_field_is_not_faked(tmp_path):
    runner = build_runner(tmp_path, None)   # _no_verifier: abstención honesta
    runner.run_task("t-noiso", "merge lists", "code_qa",
                    ["hephaestus", "verify"])
    events = _verifier_decision_events(runner)
    assert events, "no hubo evento verifier_decision en la cadena"
    assert all("sandbox_isolation" not in e for e in events)
