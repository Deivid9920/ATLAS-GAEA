"""Composite verifier. Immutable anchor.

The hero of ATLAS: a weighted vote over registered verifiers with a
hard-BLOCK override, an honest ABSTAIN when every verifier doubts, and
memoization keyed by the registry signature. The BLOCK/ABSTAIN/REVISE/
APPROVE decision is the product — never emitted without it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import MutableMapping

APPROVE = "approve"
REVISE = "revise"
BLOCK = "block"
ABSTAIN = "abstain"


@dataclass(frozen=True)
class Verdict:
    verifier: str
    score: float
    evidence: str = ""
    hard_block: bool = False


@dataclass(frozen=True)
class CompositeDecision:
    decision: str
    weighted_score: float
    votes: tuple[Verdict, ...]
    causes: tuple[str, ...]


class CompositeVerifier:
    """Weighted vote; BLOCK overrides everything; all-doubt abstains."""

    def __init__(self, tau_approve: float = 0.80,
                 tau_doubt: float = 0.35) -> None:
        if tau_doubt > tau_approve:
            raise ValueError("tau_doubt cannot exceed tau_approve")
        self.tau_approve = float(tau_approve)
        self.tau_doubt = float(tau_doubt)
        self._plugins: list = []
        self._weights: dict[str, float] = {}

    def register(self, plugin, weight: float) -> None:
        """Register a verifier plugin with its vote weight."""
        self._plugins.append(plugin)
        self._weights[plugin.name] = float(weight)

    def signature(self) -> str:
        """Hash of the registry (plugins + weights + taus); any change
        invalidates memoized verdicts."""
        payload = {
            "taus": [self.tau_approve, self.tau_doubt],
            "plugins": [[p.name, self._weights[p.name]]
                        for p in self._plugins],
        }
        return hashlib.sha256(json.dumps(
            payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def evaluate(self, claim: str,
                 context: dict | None = None) -> CompositeDecision:
        if not self._plugins:
            raise RuntimeError("no verifiers registered")

        votes = tuple(p.verify(claim, context) for p in self._plugins)

        blocks = [v for v in votes if v.hard_block]
        if blocks:
            return CompositeDecision(
                BLOCK, 0.0, votes,
                tuple(f"hard_block by {v.verifier}: "
                      f"{v.evidence or 'policy'}" for v in blocks))

        total_w = sum(self._weights[v.verifier] for v in votes)
        weighted = sum(self._weights[v.verifier] * v.score
                       for v in votes) / total_w

        causes: list[str] = [
            f"{v.verifier}: {v.score:.3f} (w={self._weights[v.verifier]:.2f})"
            f"{' — ' + v.evidence if v.evidence else ''}" for v in votes]

        if weighted >= self.tau_approve:
            decision = APPROVE
        elif all(v.score < self.tau_doubt for v in votes):
            decision = ABSTAIN
            causes.append("all verifiers doubt: honest abstention")
        else:
            decision = REVISE
            causes.append(f"weighted {weighted:.3f} < {self.tau_approve}")

        return CompositeDecision(decision, weighted, votes, tuple(causes))

    def evaluate_cached(self, claim: str, context: dict | None = None,
                        cache: MutableMapping[str, CompositeDecision] | None
                        = None) -> CompositeDecision:
        """Memoized evaluate(): the cache key binds the registry
        signature, so re-registering a verifier invalidates entries."""
        if cache is None:
            return self.evaluate(claim, context)
        key = hashlib.sha256(json.dumps(
            {"s": self.signature(),
             "c": claim,
             "x": context or {}}, sort_keys=True,
            separators=(",", ":")).encode()).hexdigest()
        if key in cache:
            return cache[key]
        decision = self.evaluate(claim, context)
        cache[key] = decision
        return decision
