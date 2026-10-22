"""MCTS with verifier pruning (FASE 4) + anytime budgets (#18).

Tree search over the profile's answer space:
  - expansion  : HEPHAESTUS generate over deterministic prompt variants
                 (config bridge.modes requested; this engine build
                 generates fp32 — honest note recorded in the report)
  - evaluation : CompositeVerifier.evaluate, MEMOIZED (#19) — each node
                 is verified exactly once
  - selection  : UCT on verified reward (c_uct from config)
  - pruning    : children whose verified score < prune_below are never
                 descended (measured against random pruning in the
                 FASE 4 report)
  - anytime    : best partial answer is always available; the search
                 stops on APPROVE, deadline or iteration cap, whichever
                 comes first

Determinism: seeded 42; child ordering and tie-breaks are stable.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from atlas_ns.bridge.hephaestus import HephaestusBridge
from atlas_ns.verify.cache import VerdictCache
from atlas_ns.verify.composite import (
    APPROVE, CompositeVerifier, Verdict)

ROOT = Path(__file__).resolve().parents[2]

_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.S)


def extract_code_block(text: str) -> str | None:
    """Last python code block in a candidate, else None (shared with
    selfplay: the MCTS node evaluation needs the executable evidence)."""
    blocks = _CODE_BLOCK.findall(text or "")
    if blocks:
        return blocks[-1].strip()
    match = re.search(r"def \w+\(.*\):.*", text or "", re.S)
    return match.group(0).strip() if match else None


PROMPT_VARIANTS = [
    "{ctx}Task: {task}\nFinal python code block only:",
    "{ctx}Task: {task}\nAnswer with the python code only:",
    "{ctx}Task: {task}\nPython code block:",
    "{ctx}Task: {task}\nCode:",
]


@dataclass
class Node:
    answer: str
    parent: "Node | None" = None
    children: list["Node"] = field(default_factory=list)
    visits: int = 0
    value: float = 0.0
    score: float = 0.0
    decision: str = "revise"
    causes: tuple[str, ...] = ()
    pruned: bool = False
    depth: int = 0
    variant: int = 0

    @property
    def mean_value(self) -> float:
        return self.value / self.visits if self.visits else self.score


class AnytimeBudget:
    """{fast, standard, deep} seconds; elapsed + iteration caps."""

    def __init__(self, seconds: float, max_iters: int | None = None):
        self.deadline = time.monotonic() + float(seconds)
        self.max_iters = max_iters
        self.iters = 0

    def expired(self) -> bool:
        if time.monotonic() >= self.deadline:
            return True
        return self.max_iters is not None and self.iters >= self.max_iters

    def tick(self) -> None:
        self.iters += 1


class VerifierMCTS:
    def __init__(self, config: dict, verifier: CompositeVerifier,
                 bridge: HephaestusBridge | None = None,
                 retriever=None) -> None:
        self.config = config
        mcts = config.get("mcts", {})
        self.branching = int(mcts.get("branching", 4))
        self.max_depth = int(mcts.get("max_depth", 6))
        self.prune_below = float(mcts.get("prune_below", 0.35))
        self.c_uct = float(mcts.get("c_uct", 1.4))
        self.budgets = dict(mcts.get("anytime_budgets_s",
                                     {"fast": 30, "standard": 300,
                                      "deep": 1800}))
        self.verifier = verifier
        self.cache = VerdictCache(verifier, int(
            config.get("verifier", {}).get("cache_size", 100000)))
        self.bridge = bridge or HephaestusBridge(
            config, repo_root=Path(__file__).resolve().parents[2])
        self.retriever = retriever
        self.prune_mode = str(mcts.get("prune_mode", "verifier"))
        self.nodes_evaluated = 0
        self.nodes_pruned = 0
        self._roots: list[Node] = []

    # -- node evaluation (memoized, the ONLY scoring path) -------------------
    def evaluate(self, answer: str, task: dict):
        """Composite verdict WITH executed evidence: the programmatic
        plugin runs the candidate's code block against the task's own
        tests inside the sandbox — measured, not assumed."""
        context: dict = {"triplets": task.get("triplets", [])}
        code = extract_code_block(answer)
        if code and task.get("tests"):
            context["code"] = code
            context["tests"] = task["tests"]
        decision = self.cache.evaluate(answer, context)
        self.nodes_evaluated += 1
        return decision

    # -- expansion -----------------------------------------------------------
    # max_seq 256 - 48 new - generous margin for heph's internal special
    # tokens (measured: a 202-token prompt overflowed at max_new=48)
    PROMPT_TOKEN_BUDGET = 160

    def _fit_prompt(self, prompt: str, task: dict) -> str:
        """Enforce the nano's context window with the REAL tokenizer.

        Fallback ladder (honest): drop retrieval context first, then
        truncate the refinement blocks; never let heph see an overflow
        (it fails loud by contract).
        """
        def _tokens(s: str) -> int:
            try:
                return len(self.bridge.tokenize(s))
            except Exception:
                return int(len(s) / 1.4) + 1

        if _tokens(prompt) <= self.PROMPT_TOKEN_BUDGET:
            return prompt
        # 1) drop the retrieval context (variants embed it at the head)
        bare = prompt
        if "</untrusted>" in bare:
            bare = bare[bare.index("</untrusted>") + len("</untrusted>"):]
            if _tokens(bare) <= self.PROMPT_TOKEN_BUDGET:
                return bare
        # 2) truncate Previous/feedback blocks
        lines = prompt.splitlines()
        kept: list[str] = []
        for line in lines:
            kept.append(line[:120])
            if _tokens("\n".join(kept)) > self.PROMPT_TOKEN_BUDGET:
                kept.pop()
                break
        trimmed = "\n".join(kept)
        if _tokens(trimmed) <= self.PROMPT_TOKEN_BUDGET:
            return trimmed
        # 3) guaranteed hard cut: head + instruction (never overflow)
        return prompt[:240].rsplit("\n", 1)[0] + "\nFinal python code block:"

    def expand_children(self, node: Node, task: dict) -> list[Node]:
        if node.depth >= self.max_depth:
            return []
        children: list[Node] = []
        if node.parent is None:
            # root: retrieval-grounded candidate FIRST (the cited
            # reference from the profile corpus — the narrow-domain
            # channel), then deterministic prompt variants for the nano
            ctx = ""
            if self.retriever is not None:
                ctx = self.retriever.context_block(task["prompt"], k=1)
                import re as _re

                blocks = _re.findall(
                    r"```python\n(.*?)```", ctx, _re.S)
                if blocks:
                    children.append(Node(
                        answer=f"```python\n{blocks[-1].strip()}\n```",
                        parent=node, depth=1, variant=-1))
            for i, variant in enumerate(
                    PROMPT_VARIANTS[:max(2, self.branching - 1)]):
                prompt = variant.format(ctx=ctx, task=task["prompt"])
                prompt = self._fit_prompt(prompt, task)
                res = self.bridge.generate(prompt, max_new_tokens=48)
                children.append(Node(answer=res["text"], parent=node,
                                     depth=node.depth + 1, variant=i))
                if len(children) >= self.branching:
                    break
            return children
        # depth > 1: verifier-guided REFINEMENT of this node's answer
        feedback = ("; ".join(node.causes[:2]) or "improve")[:120]
        prompt = (f"Task: {task['prompt']}\nPrevious:\n"
                  f"{node.answer[:160]}\n"
                  f"Fix: {feedback}\nFinal python code block:")
        prompt = self._fit_prompt(prompt, task)
        for i in range(self.branching):
            res = self.bridge.generate(prompt, max_new_tokens=48)
            children.append(Node(answer=res["text"], parent=node,
                                 depth=node.depth + 1, variant=i))
            if len(children) >= self.branching:
                break
        return children

    # -- UCT -------------------------------------------------------------------
    def select_child(self, node: Node) -> Node:
        import math

        best, best_uct = None, float("-inf")
        for child in node.children:
            if child.visits == 0:
                return child  # unexplored first (deterministic order)
            uct = child.mean_value + self.c_uct * math.sqrt(
                math.log(max(node.visits, 2)) / child.visits)
            if uct > best_uct:
                best, best_uct = child, uct
        return best or node.children[0]

    # -- anytime best answer ------------------------------------------------------
    def best_answer(self) -> tuple[str, float, str]:
        """Best partial answer among evaluated nodes (never empty)."""
        best_node, best_key = None, (-1.0, "")
        stack = list(self._roots)
        while stack:
            node = stack.pop()
            if node.visits > 0:
                key = (node.score, -node.depth)
                if key > best_key:
                    best_node, best_key = node, key
            stack.extend(node.children)
        if best_node is None:
            return "", 0.0, "abstain"
        return best_node.answer, best_node.score, best_node.decision

    # -- search ---------------------------------------------------------------------
    def search(self, task: dict, budget: str = "standard",
               max_iters: int | None = None) -> dict:
        seconds = float(self.budgets.get(budget, 30))
        clock = AnytimeBudget(seconds, max_iters)
        # per-search counters: the pruning comparison needs clean numbers
        self.nodes_evaluated = 0
        self.nodes_pruned = 0
        root = Node(answer="", depth=0)
        self._roots = [root]
        approved: Node | None = None

        while not clock.expired() and approved is None:
            clock.tick()
            node = root
            # descend by UCT until an expandable node
            while node.children and node.depth < self.max_depth:
                nxt = self.select_child(node)
                if nxt is node:
                    break
                node = nxt
            # expand + evaluate the sibling batch
            children = self.expand_children(node, task)
            if not children:
                # dead end: mark visited, continue with best partial
                node.visits += 1
                node.value += node.score
                break
            for child in children:
                d = self.evaluate(child.answer, task)
                child.score = d.weighted_score
                child.decision = d.decision
                child.causes = d.causes
                child.visits, child.value = 1, d.weighted_score
                # backpropagate
                walker = child
                while walker is not None:
                    walker.visits += 1
                    walker.value += d.weighted_score
                    walker = walker.parent
                # pruning decision
                if self.prune_mode == "random":
                    # baseline: seeded stable coin at the same floor,
                    # ignoring the verifier score for PRUNING (the
                    # verifier still scores for answer selection)
                    import hashlib

                    stable = int(hashlib.md5(
                        child.answer.encode()).hexdigest()[:8], 16)
                    prune_it = (stable % 1000 / 1000.0) \
                        < self.prune_below
                elif child.score < self.prune_below:
                    prune_it = True
                else:
                    prune_it = False
                if prune_it:
                    child.pruned = True
                    self.nodes_pruned += 1   # never descended
                elif child.decision == APPROVE and approved is None:
                    approved = child
            # keep only non-pruned children for future descent
            node.children = [c for c in children if not c.pruned]

        answer, score, decision = (approved.answer, approved.score,
                                   approved.decision) if approved \
            else self.best_answer()
        return {
            "answer": answer,
            "score": round(score, 4),
            "decision": decision,
            "nodes_evaluated": self.nodes_evaluated,
            "nodes_pruned": self.nodes_pruned,
            "iterations": clock.iters,
            "cache_stats": self.cache.stats(),
            "budget": budget,
            "seed": 42,
        }


def load_config(path: str | Path = "config.yaml") -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
