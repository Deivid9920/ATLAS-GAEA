"""FASE 4: MCTS with verifier pruning + anytime budgets (fast fakes)."""
from pathlib import Path

import pytest
import yaml

from atlas_ns.mcts.search import AnytimeBudget, Node, VerifierMCTS
from atlas_ns.verify.composite import CompositeVerifier, Verdict

ROOT = Path(__file__).resolve().parents[1]


class FakeBridge:
    """Deterministic candidates: variant 0 correct, others broken."""

    def __init__(self, good: str, bad: str):
        self.good, self.bad = good, bad
        self.calls = 0

    def generate(self, prompt: str, max_new_tokens: int = 48) -> dict:
        self.calls += 1
        # variant 0 gets the good candidate; the rest garbage
        text = self.good if self.calls % max(2, 4) == 1 else self.bad
        return {"text": text}


class PassComposite(CompositeVerifier):
    """Composite that approves everything above the floor."""

    def __init__(self):
        super().__init__(0.8, 0.35)
        self._evaluated: list[str] = []

    def evaluate(self, claim, context=None):
        from atlas_ns.verify.composite import CompositeDecision

        self._evaluated.append(claim)
        votes = (Verdict("programmatic", 1.0, "", False),)
        return CompositeDecision("approve", 1.0, votes, ("fixture",))


@pytest.fixture()
def config():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    cfg["mcts"] = {"anytime_budgets_s": {"fast": 1, "standard": 5,
                                         "deep": 10},
                   "branching": 4, "max_depth": 2, "prune_below": 0.35,
                   "c_uct": 1.4, "memoize": True}
    return cfg


GOOD = "```python\ndef ok():\n    return 42\n```"
BAD = "```python\ndef broken(:\n  syntax error\n```"


def test_anytime_budget_deadline():
    budget = AnytimeBudget(0.05, max_iters=10_000_000)
    import time

    time.sleep(0.06)
    assert budget.expired()


def test_anytime_budget_iteration_cap():
    budget = AnytimeBudget(1000, max_iters=3)
    for _ in range(3):
        budget.tick()
    assert budget.expired()


def test_mcts_stops_on_approve_and_returns_best(config):
    bridge = FakeBridge(GOOD, BAD)
    mcts = VerifierMCTS(config, PassComposite(), bridge=bridge)
    task = {"prompt": "return 42", "triplets": []}
    result = mcts.search(task, budget="fast", max_iters=4)
    assert result["decision"] == "approve"
    assert result["answer"] == GOOD
    assert result["nodes_evaluated"] <= 4 * 2  # budget bounded
    assert "cache_stats" in result and result["seed"] == 42


def test_mcts_prunes_below_floor(config):
    class RejectLow(PassComposite):
        def evaluate(self, claim, context=None):
            from atlas_ns.verify.composite import CompositeDecision

            self._evaluated.append(claim)
            good = claim == GOOD
            votes = (Verdict("programmatic",
                             1.0 if good else 0.1, "", False),)
            return CompositeDecision(
                "approve" if good else "revise",
                1.0 if good else 0.1, votes, ("fixture",))

    bridge = FakeBridge(GOOD, BAD)
    mcts = VerifierMCTS(config, RejectLow(), bridge=bridge)
    task = {"prompt": "x", "triplets": []}
    result = mcts.search(task, budget="fast", max_iters=3)
    assert result["nodes_pruned"] > 0  # the 0.1-scored child was cut


def test_memoized_evaluation_hits_cache(config):
    bridge = FakeBridge(GOOD, BAD)
    mcts = VerifierMCTS(config, PassComposite(), bridge=bridge)
    task = {"prompt": "same", "triplets": []}
    mcts.search(task, budget="fast", max_iters=2)
    # identical candidate text across iterations -> cache hits
    assert mcts.cache.stats()["hits"] >= 1


def test_best_answer_never_empty_on_dead_end(config):
    class AllRevise(PassComposite):
        def evaluate(self, claim, context=None):
            from atlas_ns.verify.composite import CompositeDecision

            self._evaluated.append(claim)
            votes = (Verdict("programmatic", 0.5, "", False),)
            return CompositeDecision("revise", 0.5, votes, ("meh",))

    mcts = VerifierMCTS(config, AllRevise(), bridge=FakeBridge(GOOD, BAD))
    task = {"prompt": "x", "triplets": []}
    result = mcts.search(task, budget="fast", max_iters=1)
    assert result["answer"] != ""       # anytime: partial always available
    assert result["decision"] == "revise"


def test_max_depth_bounds_expansion(config):
    class DeepSpy(PassComposite):
        pass

    mcts = VerifierMCTS(config, DeepSpy(), bridge=FakeBridge(GOOD, BAD))
    node = Node(answer=GOOD, depth=config["mcts"]["max_depth"])
    assert mcts.expand_children(node, {"prompt": "x"}) == []
