"""Anchors for the orchestrator machine. Immutable."""
import pytest

from atlas_ns.orchestrator.machine import (
    Action, IllegalTransition, Status, Task, step)


def make_task(**kw):
    return Task(task_id="t1", goal="g", profile="code_qa", **kw)


def happy_path():
    t, a = step(make_task(), {"kind": "plan_ready",
                              "plan": ["hephaestus", "verify"]})
    assert t.status == Status.ACTING and a.kind == "call_tool"
    t, a = step(t, {"kind": "tool_result", "output": "answer"})
    assert t.status == Status.VERIFYING
    t, a = step(t, {"kind": "decision", "decision": "approve"})
    assert t.status == Status.COMMITTED and a.kind == "emit"
    return t


def test_full_happy_path():
    happy_path()


def test_revise_loop_then_approve():
    t, _ = step(make_task(), {"kind": "plan_ready", "plan": ["t1", "t2"]})
    t, _ = step(t, {"kind": "tool_result", "output": "bad"})
    t, a = step(t, {"kind": "decision", "decision": "revise",
                    "reason": "weak"})
    assert t.status == Status.ACTING and t.attempts == 1
    assert "feedback" in a.args
    t, _ = step(t, {"kind": "tool_result", "output": "better"})
    t, _ = step(t, {"kind": "decision", "decision": "approve"})
    assert t.status == Status.COMMITTED


def test_attempt_cap_fails():
    t, _ = step(make_task(max_attempts=2), {"kind": "plan_ready",
                                            "plan": ["t"]})
    t, _ = step(t, {"kind": "tool_result", "output": "x"})
    t, _ = step(t, {"kind": "decision", "decision": "revise"})
    t, _ = step(t, {"kind": "tool_result", "output": "y"})
    t, a = step(t, {"kind": "decision", "decision": "revise"})
    assert t.status == Status.FAILED and a.kind == "fail"


def test_abstain_path():
    t, _ = step(make_task(), {"kind": "plan_ready", "plan": ["t"]})
    t, _ = step(t, {"kind": "tool_result", "output": "?"})
    t, a = step(t, {"kind": "decision", "decision": "abstain",
                    "reason": "all doubt"})
    assert t.status == Status.ABSTAINED and a.kind == "abstain"


def test_budget_exhaustion():
    t, _ = step(make_task(step_budget=1), {"kind": "plan_ready",
                                           "plan": ["t"]})
    t, a = step(t, {"kind": "tool_result", "output": "x"})
    assert t.status == Status.BUDGET_EXHAUSTED and a.kind == "wait"


def test_resumability_roundtrip():
    t, _ = step(make_task(), {"kind": "plan_ready", "plan": ["t"]})
    t, _ = step(t, {"kind": "tool_result", "output": "x"})
    t2 = Task.from_record(t.to_record())
    assert t2 == t
    t3, _ = step(t2, {"kind": "decision", "decision": "approve"})
    assert t3.status == Status.COMMITTED


def test_illegal_transitions():
    with pytest.raises(IllegalTransition):
        step(make_task(), {"kind": "tool_result"})     # no plan yet
    t, _ = step(make_task(), {"kind": "plan_ready", "plan": ["t"]})
    with pytest.raises(IllegalTransition):
        step(t, {"kind": "decision", "decision": "approve"})  # not verifying
    done = happy_path()
    with pytest.raises(IllegalTransition):
        step(done, {"kind": "plan_ready", "plan": ["t"]})
