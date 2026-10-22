"""Verdict memoization (#19 ANCLA) with signature invalidation.

Wraps CompositeVerifier.evaluate_cached with a bounded cache whose key
binds the registry signature: re-registering ANY verifier invalidates
every entry (the anchor's guarantee, made operational). LRU eviction
at config.verifier.cache_size; hit/miss counters are measured, never
assumed.
"""

from __future__ import annotations

from collections import OrderedDict

from atlas_ns.verify.composite import CompositeVerifier


class VerdictCache:
    def __init__(self, verifier: CompositeVerifier, capacity: int = 100000):
        if capacity <= 0:
            raise ValueError("cache capacity must be positive")
        self._verifier = verifier
        self._capacity = capacity
        self._store: OrderedDict[str, object] = OrderedDict()
        self._signature = verifier.signature()
        self.hits = 0
        self.misses = 0

    def evaluate(self, claim: str, context: dict | None = None):
        if self._verifier.signature() != self._signature:
            # registry changed underneath us: invalidate EVERYTHING
            self._store.clear()
            self._signature = self._verifier.signature()
        return self._lookup(claim, context)

    def _lookup(self, claim: str, context: dict | None):
        import hashlib
        import json

        key = hashlib.sha256(json.dumps(
            {"s": self._signature, "c": claim, "x": context or {}},
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if key in self._store:
            self.hits += 1
            self._store.move_to_end(key)
            return self._store[key]
        self.misses += 1
        decision = self._verifier.evaluate(claim, context)
        self._store[key] = decision
        while len(self._store) > self._capacity:
            self._store.popitem(last=False)
        return decision

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0

    def stats(self) -> dict:
        return {"hits": self.hits, "misses": self.misses,
                "entries": len(self._store),
                "hit_rate": round(self.hit_rate, 4),
                "signature": self._signature[:12]}


def attached_cache(verifier: CompositeVerifier, capacity: int) -> VerdictCache:
    """Wire the cache to a verifier; the verifier stays the ANCLA."""
    return VerdictCache(verifier, capacity)
