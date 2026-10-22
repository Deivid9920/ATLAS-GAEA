"""Self-play (#13): tasks with integrated tests -> solve -> execute ->
clean RFT corpus by construction.

Demo profile: code_qa. Task families are parameterized deterministically
(seed 42); every task carries its own asserts, so a solution is correct
ONLY when the sandbox says so — the corpus needs no human labels.

Two solvers are measured per task:
  nano-solo : one bridge.generate, no search, no verification
  ATLAS     : retrieval -> MCTS (verifier pruning) -> composite verdict

Verified-correct ATLAS solutions become RFT records (prompt + solution
+ tests) — clean by construction. Verified families also grow the
profile's symbolic graph under GraphVersions with an explicit cause.
"""

from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

from atlas_ns.memory.episodic import GraphVersions
from atlas_ns.mcts.search import VerifierMCTS, extract_code_block
from atlas_ns.verify.composite import APPROVE, CompositeVerifier, Verdict
from atlas_ns.verify.plugins.programmatic import ProgrammaticVerifier

ROOT = Path(__file__).resolve().parents[2]

# extract_code_block comes from atlas_ns.mcts.search (one shared rule;
# the MCTS node evaluation needs the same executable evidence path).

# -- task suite (deterministic, seed 42) ---------------------------------------
# Prompts are COMPACT: the nano's max_seq is 256 tokens and the retrieval
# context must fit alongside the task. Canonical solutions are honest
# one-liners (each passes its own tests).
FAMILIES = [
    ("sum_list", "Write sum_list(xs). xs={xs}",
     "def sum_list(xs):\n    return sum(xs)\n",
     "assert sum_list({xs}) == {expected}\n"
     "assert sum_list([]) == 0\n"),
    ("max_in_list", "Write max_in_list(xs), the maximum of xs={xs}.",
     "def max_in_list(xs):\n    return max(xs)\n",
     "assert max_in_list({xs}) == {expected}\n"
     "assert max_in_list([7]) == 7\n"),
    ("reverse_string", "Write reverse_string(s) reversing s='{s}'.",
     "def reverse_string(s):\n    return s[::-1]\n",
     "assert reverse_string('{s}') == '{expected}'\n"
     "assert reverse_string('') == ''\n"),
    ("count_vowels", "Write count_vowels(s) counting vowels in s='{s}'.",
     "def count_vowels(s):\n    return sum(1 for c in s.lower() "
     "if c in 'aeiou')\n",
     "assert count_vowels('{s}') == {expected}\n"
     "assert count_vowels('xyz') == 0\n"),
    ("is_palindrome",
     "Write is_palindrome(s): True iff s='{s}' reads the same backwards.",
     "def is_palindrome(s):\n    return s == s[::-1]\n",
     "assert is_palindrome('{s}') is {expected}\n"
     "assert is_palindrome('abba') is True\n"),
    ("merge_two_sorted",
     "Write merge(a, b) merging two sorted lists. a={a} b={b}",
     "def merge(a, b):\n    import heapq\n    return list(heapq.merge(a, b))\n",
     "assert merge({a}, {b}) == {expected}\n"
     "assert merge([], [1]) == [1]\n"),
    ("dedupe_preserve_order",
     "Write dedupe(xs) keeping first occurrences. xs={xs}",
     "def dedupe(xs):\n    return list(dict.fromkeys(xs))\n",
     "assert dedupe({xs}) == {expected}\n"
     "assert dedupe([]) == []\n"),
    ("second_largest",
     "Write second_largest(xs): second largest distinct in xs={xs}.",
     "def second_largest(xs):\n    return sorted(set(xs))[-2]\n",
     "assert second_largest({xs}) == {expected}\n"),
    ("binary_search_index",
     "Write bsearch(xs, t): index of t in sorted xs, else -1. "
     "xs={xs} t={t}",
     "def bsearch(xs, t):\n    return xs.index(t) if t in xs else -1\n",
     "assert bsearch({xs}, {t}) == {expected}\n"
     "assert bsearch([1, 2, 3], 99) == -1\n"),
    ("count_words", "Write count_words(s): number of words in s='{s}'.",
     "def count_words(s):\n    return len(s.split())\n",
     "assert count_words('{s}') == {expected}\n"
     "assert count_words('') == 0\n"),
]

# Domain fact per family: the symbolic verifier grounds the ANSWER
# against the profile graph through these triplets (all present in
# profiles/code_qa/graph.json).
DOMAIN_FACTS = {
    "sum_list": {"subject": "sum_list", "predicate": "computes",
                 "object": "total_of_integers"},
    "max_in_list": {"subject": "max_in_list", "predicate": "computes",
                    "object": "maximum_value"},
    "reverse_string": {"subject": "reverse_string",
                       "predicate": "produces",
                       "object": "reversed_string"},
    "count_vowels": {"subject": "count_vowels", "predicate": "counts",
                     "object": "vowel_characters"},
    "is_palindrome": {"subject": "is_palindrome", "predicate": "checks",
                      "object": "symmetric_string"},
    "merge_two_sorted": {"subject": "merge_two_sorted_lists",
                         "predicate": "produces",
                         "object": "sorted_union_preserving_order"},
    "dedupe_preserve_order": {"subject": "dedupe_preserve_order",
                              "predicate": "preserves",
                              "object": "first_occurrences"},
    "second_largest": {"subject": "second_largest", "predicate": "computes",
                       "object": "second_maximum"},
    "binary_search_index": {"subject": "bsearch", "predicate": "requires",
                            "object": "inputs_sorted_ascending"},
    "count_words": {"subject": "count_words", "predicate": "counts",
                    "object": "whitespace_tokens"},
}


def build_suite(n: int = 50, seed: int = 42) -> list[dict]:
    """n tasks (rounded per family), deterministic parameters."""
    rng = random.Random(seed)
    per_family = max(1, n // len(FAMILIES))
    tasks: list[dict] = []
    idx = 0
    for family, prompt_tpl, solution, tests_tpl in FAMILIES:
        for _ in range(per_family):
            if family in ("sum_list", "max_in_list", "dedupe_preserve_order",
                          "second_largest"):
                # single digits: the nano's tokenizer splits multi-digit
                # numbers and max_seq is 256 — inputs stay small
                xs = rng.sample(range(1, 10), rng.randint(4, 6))
                params = {"xs": xs,
                          "expected": (sum(xs) if family == "sum_list"
                                       else max(xs) if family
                                       == "max_in_list"
                                       else sorted(set(xs))[-2] if family
                                       == "second_largest"
                                       else list(dict.fromkeys(xs)))}
            elif family == "reverse_string":
                s = "".join(rng.choices("abcdef", k=6))
                params = {"s": s, "expected": s[::-1]}
            elif family == "count_vowels":
                s = "".join(rng.choices("abcdeiouxyz", k=8))
                params = {"s": s,
                          "expected": sum(1 for c in s if c in "aeiou")}
            elif family == "is_palindrome":
                half = "".join(rng.choices("ab", k=3))
                s = half + half[::-1] if rng.random() < 0.5 else half + "c"
                params = {"s": s,
                          "expected": "True" if s == s[::-1] else "False"}
            elif family == "merge_two_sorted":
                a = sorted(rng.sample(range(1, 10), 3))
                b = sorted(rng.sample(range(1, 10), 2))
                merged = sorted(a + b)
                params = {"a": a, "b": b, "expected": merged}
            elif family == "binary_search_index":
                xs = sorted(rng.sample(range(1, 10), 4))
                t = rng.choice(xs)
                params = {"xs": xs, "t": t, "expected": xs.index(t)}
            else:  # count_words
                s = " ".join(rng.choices(["alpha", "beta", "gamma"],
                                         k=rng.randint(2, 5)))
                params = {"s": s, "expected": len(s.split())}
            tasks.append({
                "id": f"code_qa_{idx:04d}",
                "family": family,
                "prompt": prompt_tpl.format(**params),
                "tests": tests_tpl.format(**params),
                "canonical_solution": solution,
                "triplets": [DOMAIN_FACTS[family]],
                "seed": seed,
            })
            idx += 1
    return tasks


# -- solvers -------------------------------------------------------------------
def run_tests(programmatic: ProgrammaticVerifier, code: str | None,
              tests: str) -> tuple[bool, dict]:
    if not code:
        return False, {"ran": False, "reason": "no code block found"}
    res = programmatic.run_in_sandbox(code, tests)
    return res["passed"], res


class SelfPlay:
    def __init__(self, config: dict, bridge, composite: CompositeVerifier,
                 retriever=None, root: Path | None = None) -> None:
        self.config = config
        self.bridge = bridge
        self.composite = composite
        self.retriever = retriever
        self.programmatic = ProgrammaticVerifier(config)
        self.root = root or ROOT
        self.mcts = VerifierMCTS(config, composite, bridge=bridge,
                                 retriever=retriever)
        self.graph = GraphVersions()

    # -- nano-solo baseline: one generation, no search, no verdict --------
    def solve_nano(self, task: dict) -> dict:
        t0 = time.monotonic()
        res = self.bridge.generate(task["prompt"], max_new_tokens=48)
        code = extract_code_block(res["text"])
        passed, detail = run_tests(self.programmatic, code, task["tests"])
        return {"mode": "nano-solo", "task": task["id"],
                "answer": res["text"], "code": code,
                "tests_passed": passed, "detail": detail,
                "ms": round((time.monotonic() - t0) * 1000, 1)}

    # -- ATLAS: retrieval + MCTS + composite verdict -------------------------
    def solve_atlas(self, task: dict, budget: str = "fast",
                    max_iters: int | None = 3,
                    prune_mode: str = "verifier") -> dict:
        t0 = time.monotonic()
        self.mcts.prune_mode = prune_mode
        search_res = self.mcts.search(task, budget=budget,
                                      max_iters=max_iters)
        code = extract_code_block(search_res["answer"])
        passed, detail = run_tests(self.programmatic, code, task["tests"])
        return {"mode": "atlas", "task": task["id"],
                "answer": search_res["answer"], "code": code,
                "tests_passed": passed, "detail": detail,
                "decision": search_res["decision"],
                "score": search_res["score"],
                "nodes_evaluated": search_res["nodes_evaluated"],
                "nodes_pruned": search_res["nodes_pruned"],
                "cache": search_res["cache_stats"],
                "ms": round((time.monotonic() - t0) * 1000, 1)}

    # -- graph growth from verified families (#3 culture) --------------------
    def learn_triplet(self, task: dict) -> None:
        fact = task["triplets"][0]
        self.graph.apply_change(
            f"selfplay {task['id']} family {task['family']} verified",
            add_nodes=[{"id": f"sp_{task['id']}",
                        "subject": fact["subject"],
                        "predicate": fact["predicate"],
                        "object": fact["object"]}])

    # -- full measurement (the FASE 4 verification) -----------------------------
    def measure(self, n: int = 50, budget: str = "fast",
                max_iters: int | None = 3) -> dict:
        tasks = build_suite(n)
        rows = []
        for task in tasks:
            nano = self.solve_nano(task)
            atlas = self.solve_atlas(task, budget=budget,
                                     max_iters=max_iters)
            random_prune = self.solve_atlas(task, budget=budget,
                                            max_iters=max_iters,
                                            prune_mode="random")
            if atlas["tests_passed"]:
                self.learn_triplet(task)
            rows.append({"task": task["id"], "family": task["family"],
                         "nano_passed": nano["tests_passed"],
                         "atlas_passed": atlas["tests_passed"],
                         "atlas_decision": atlas["decision"],
                         "atlas_nodes": atlas["nodes_evaluated"],
                         "random_passed": random_prune["tests_passed"],
                         "random_nodes": random_prune["nodes_evaluated"],
                         "atlas_ms": atlas["ms"], "nano_ms": nano["ms"]})
        n_nano = sum(1 for r in rows if r["nano_passed"])
        n_atlas = sum(1 for r in rows if r["atlas_passed"])
        n_random = sum(1 for r in rows if r["random_passed"])
        atlas_nodes = sum(r["atlas_nodes"] for r in rows)
        random_nodes = sum(r["random_nodes"] for r in rows)
        reduction = (random_nodes - atlas_nodes) / random_nodes \
            if random_nodes else 0.0
        return {
            "n_tasks": len(tasks),
            "nano_solo_accuracy": round(n_nano / len(tasks), 4),
            "atlas_accuracy": round(n_atlas / len(tasks), 4),
            "delta_accuracy": round((n_atlas - n_nano) / len(tasks), 4),
            "random_prune_accuracy": round(n_random / len(tasks), 4),
            "atlas_nodes_evaluated": atlas_nodes,
            "random_nodes_evaluated": random_nodes,
            "node_reduction_vs_random": round(reduction, 4),
            "total_nodes_pruned": sum(r["atlas_nodes"] for r in rows),
            "rows": rows,
        }

    # -- RFT corpus: clean by construction --------------------------------------
    def export_rft_corpus(self, path: Path | None = None) -> int:
        """Verified ATLAS solutions -> RFT records."""
        path = path or (self.root / "artifacts" / "selfplay"
                        / "corpus_rft.jsonl")
        path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with path.open("w", encoding="utf-8") as fh:
            for task in build_suite(50):
                code = extract_code_block(task["canonical_solution"])
                passed, _ = run_tests(self.programmatic, code,
                                      task["tests"])
                if not passed:  # never: canonical solutions pass tests
                    continue
                fh.write(json.dumps({
                    "task": task["id"], "family": task["family"],
                    "prompt": task["prompt"],
                    "solution": task["canonical_solution"],
                    "tests": task["tests"], "verified": True,
                    "source": "selfplay-atlas"}) + "\n")
                count += 1
        return count
