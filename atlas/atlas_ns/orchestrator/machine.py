"""Orchestrator state machine. Immutable anchor.

Pure lifecycle for tasks: RECEIVED -> ACTING -> VERIFYING -> one of
{COMMITTED, ABSTAINED, FAILED, BUDGET_EXHAUSTED}. step() is a pure
function over frozen dataclasses; every transition is deterministic
and auditable, and tasks serialize to/from records so a killed run can
resume exactly where it stopped (#17).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any


class Status(Enum):
    RECEIVED = "received"
    ACTING = "acting"
    VERIFYING = "verifying"
    REVISING = "revising"           # transient; never persisted
    COMMITTED = "committed"
    ABSTAINED = "abstained"
    FAILED = "failed"
    BUDGET_EXHAUSTED = "budget_exhausted"


class IllegalTransition(Exception):
    """Raised when an event is not valid for the task's current status."""


@dataclass(frozen=True)
class Action:
    kind: str                       # wait | call_tool | emit | abstain | fail
    tool: str | None = None
    args: dict | None = None
    payload: Any = None


@dataclass(frozen=True)
class Task:
    task_id: str
    goal: str
    profile: str
    max_attempts: int = 3
    step_budget: int = 64
    status: Status = Status.RECEIVED
    plan: tuple[str, ...] = ()
    steps_used: int = 0
    attempts: int = 0
    result: Any = None
    cause: str | None = None

    def to_record(self) -> dict:
        """JSON-able snapshot for crash-resumable persistence (#17)."""
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "profile": self.profile,
            "max_attempts": self.max_attempts,
            "step_budget": self.step_budget,
            "status": self.status.value,
            "plan": list(self.plan),
            "steps_used": self.steps_used,
            "attempts": self.attempts,
            "result": self.result,
            "cause": self.cause,
        }

    @classmethod
    def from_record(cls, rec: dict) -> "Task":
        return cls(
            task_id=rec["task_id"],
            goal=rec["goal"],
            profile=rec["profile"],
            max_attempts=rec["max_attempts"],
            step_budget=rec["step_budget"],
            status=Status(rec["status"]),
            plan=tuple(rec["plan"]),
            steps_used=rec["steps_used"],
            attempts=rec["attempts"],
            result=rec["result"],
            cause=rec["cause"],
        )


def step(task: Task, event: dict) -> tuple[Task, Action]:
    """Pure transition: (task, event) -> (next task, action to perform).

    Events: plan_ready | tool_result | decision | crash_recover. The
    caller executes the returned Action; the machine never does I/O.
    """
    status, kind = task.status, event.get("kind", "")

    if status in (Status.COMMITTED, Status.ABSTAINED, Status.FAILED,
                  Status.BUDGET_EXHAUSTED):
        raise IllegalTransition(f"terminal status {status.value}")

    if kind == "crash_recover":
        return task, Action("wait")

    if status == Status.RECEIVED:
        if kind != "plan_ready":
            raise IllegalTransition(kind)
        plan = tuple(event["plan"])
        if not plan:
            return replace(task, status=Status.FAILED,
                                cause="empty plan"), Action("fail",
                                                           payload="")
        return replace(task, status=Status.ACTING, plan=plan,
                            cause=None), Action("call_tool",
                                                tool=plan[0],
                                                args=event.get("args", {}))

    if status == Status.ACTING:
        if kind == "tool_result":
            next_steps = task.steps_used + 1
            if next_steps >= task.step_budget:
                return replace(task, status=Status.BUDGET_EXHAUSTED,
                                    steps_used=next_steps,
                                    cause="step budget spent"), \
                    Action("wait")
            return replace(task, status=Status.VERIFYING,
                                steps_used=next_steps,
                                result=event.get("output")), Action("wait")
        raise IllegalTransition(kind)

    if status == Status.VERIFYING:
        verdict = event.get("decision")
        if verdict == "approve":
            return replace(task, status=Status.COMMITTED), Action(
                "emit", payload=task.result)
        if verdict == "abstain":
            return replace(task, status=Status.ABSTAINED,
                                cause=event.get(
                                    "reason", "verifier abstention")), \
                Action("abstain", payload=event.get("reason"))
        if verdict in ("revise", "block"):
            if task.attempts + 1 >= task.max_attempts:
                return replace(task, status=Status.FAILED,
                                    attempts=task.attempts + 1,
                                    cause=f"{verdict} at attempt cap"), \
                    Action("fail", payload=event.get("reason"))
            plan = task.plan
            return replace(task, status=Status.ACTING,
                                attempts=task.attempts + 1), Action(
                "call_tool", tool=plan[min(task.attempts + 1,
                                           len(plan) - 1)],
                args={"feedback": event.get("reason", ""),
                      "previous": task.result})
        raise IllegalTransition(str(verdict))

    if status == Status.REVISING:
        raise IllegalTransition("revising is transient; use ACTING")

    raise IllegalTransition(f"unhandled {status}/{kind}")

