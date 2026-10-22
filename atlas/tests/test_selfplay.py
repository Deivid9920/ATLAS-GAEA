"""FASE 4: self-play — suite construction, both solvers, RFT corpus."""
from pathlib import Path

import pytest
import yaml

from atlas_ns.mcts.selfplay import (
    SelfPlay, build_suite, extract_code_block, run_tests)
from atlas_ns.verify.composite import CompositeVerifier, Verdict
from atlas_ns.verify.plugins.programmatic import ProgrammaticVerifier

ROOT = Path(__file__).resolve().parents[1]


class FakeBridge:
    """Echoes the canonical solution in a code block (variant 0) or
    returns garbage depending on the prompt's task text."""

    def generate(self, prompt: str, max_new_tokens: int = 48) -> dict:
        if "retrieved" in prompt.lower() or "[doc:" in prompt:
            # ATLAS path: with retrieval context, echo the doc's code
            import re

            blocks = re.findall(r"```python\n(.*?)```", prompt, re.S)
            if blocks:
                return {"text": f"```python\n{blocks[-1].strip()}\n```"}
        return {"text": "I cannot write code, sorry: IGIGI"}


def approving_composite():
    cv = CompositeVerifier(0.8, 0.35)

    class P:
        def __init__(self, name):
            self.name = name

        def verify(self, claim, context):
            return Verdict(self.name, 0.9, "fixture", False)

    cv.register(P("programmatic"), 0.45)
    cv.register(P("symbolic"), 0.35)
    cv.register(P("probe"), 0.20)
    return cv


# -- suite -------------------------------------------------------------------
def test_suite_has_50_tasks_with_integrated_tests():
    tasks = build_suite(50)
    assert len(tasks) == 50
    assert all(t["tests"].startswith("assert") for t in tasks)
    assert len({t["id"] for t in tasks}) == 50


def test_suite_deterministic_seed_42():
    a = build_suite(50)
    b = build_suite(50)
    assert a == b


def test_canonical_solutions_pass_their_own_tests():
    """The suite is self-consistent: every canonical solution passes."""
    programmatic = ProgrammaticVerifier()
    for task in build_suite(50):
        code = extract_code_block(
            f"```python\n{task['canonical_solution']}\n```")
        passed, detail = run_tests(programmatic, code, task["tests"])
        assert passed, f"{task['id']} canonical failed: {detail}"


# -- extract ---------------------------------------------------------------
def test_extract_code_block_prefers_last_block():
    text = "```python\ndef a():\n    pass\n```\nnoise\n```python\ndef b():\n    return 1\n```"
    assert extract_code_block(text).startswith("def b()")


def test_extract_none_on_garbage():
    assert extract_code_block("IGIGI no code here") is None


# -- solvers with retrieval ----------------------------------------------------
@pytest.fixture()
def selfplay():
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    config["mcts"]["max_depth"] = 1
    from atlas_ns.mcts.retrieval import HybridRetriever

    retriever = HybridRetriever(ROOT / "profiles" / "code_qa" / "docs",
                                ROOT / "profiles" / "code_qa" / "graph.json")
    return SelfPlay(config, FakeBridge(), approving_composite(),
                    retriever=retriever, root=ROOT)


def test_nano_solo_honest_failure(selfplay):
    tasks = build_suite(1)
    result = selfplay.solve_nano(tasks[0])
    assert result["mode"] == "nano-solo"
    assert result["tests_passed"] is False  # garbage in, measured 0


def test_atlas_solves_via_retrieval_and_search(selfplay):
    tasks = [t for t in build_suite(50)
             if t["family"] in ("merge_two_sorted", "count_vowels")]
    result = selfplay.solve_atlas(tasks[0], budget="fast", max_iters=2)
    assert result["mode"] == "atlas"
    assert result["tests_passed"] is True
    assert result["decision"] == "approve"
    assert result["nodes_evaluated"] >= 1


def test_atlas_beats_nano_solo_on_subset(selfplay):
    tasks = build_suite(10)
    nano = [selfplay.solve_nano(t)["tests_passed"] for t in tasks]
    atlas = [selfplay.solve_atlas(t, max_iters=2)["tests_passed"]
             for t in tasks]
    assert sum(atlas) > sum(nano)  # the SYSTEM, not the nano


def test_learn_triplet_records_cause(selfplay):
    tasks = build_suite(1)
    selfplay.learn_triplet(tasks[0])
    entry = selfplay.graph.history[-1]
    assert entry["cause"].startswith(f"selfplay {tasks[0]['id']}")


def test_rft_corpus_export_clean_by_construction(selfplay, tmp_path):
    count = selfplay.export_rft_corpus(tmp_path / "corpus.jsonl")
    lines = (tmp_path / "corpus.jsonl").read_text().strip().splitlines()
    assert count == 50 and len(lines) == 50
    import json

    record = json.loads(lines[0])
    assert record["verified"] is True and record["source"] == "selfplay-atlas"
    assert record["tests"].startswith("assert")
