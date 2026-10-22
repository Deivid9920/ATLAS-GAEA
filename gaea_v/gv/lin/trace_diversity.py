"""trace_diversity: colapso de modo sobre trazas (FASE 5.e).

MinHash (k=64 permutaciones, semilla congelada) sobre shingles de
palabras de cada traza; clustering voraz por umbral de Jaccard; dos
lecturas congeladas:
  - cluster_entropy: entropia de Shannon normalizada de los tamanos de
    cluster (0 = una sola traza de modo, 1 = dispersion maxima).
  - pairwise_diversity: 1 - media de Jaccard estimada entre pares
    distintos de clusters (representantes), en [0, 1].
La regla de promocion heredada de NS: si la diversidad de trazas de
la ronda cae mas de 20% respecto del baseline, la ronda no promueve.
"""

from __future__ import annotations

import hashlib
import math
from collections import Counter

N_PERM = 64
SHINGLE = 3
SEED = 20260922


def _shingles(text: str, k: int = SHINGLE) -> set:
    words = (text or "").lower().split()
    if not words:
        return set()
    if len(words) < k:
        return {" ".join(words)}
    return {" ".join(words[i:i + k]) for i in
            range(len(words) - k + 1)}


def _hash_shingle(shingle: str, salt: int) -> int:
    payload = f"{salt}:{shingle}".encode("utf-8")
    return int.from_bytes(
        hashlib.blake2b(payload, digest_size=8).digest(), "big")


def minhash_signature(text: str, n_perm: int = N_PERM,
                       seed: int = SEED) -> tuple:
    shingles = _shingles(text)
    if not shingles:
        return tuple([0] * n_perm)
    sig = []
    for salt in range(n_perm):
        sig.append(min(_hash_shingle(s, salt) for s in shingles))
    return tuple(sig)


def estimated_jaccard(sig_a: tuple, sig_b: tuple) -> float:
    if len(sig_a) != len(sig_b) or not sig_a:
        return 0.0
    eq = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return eq / len(sig_a)


def cluster(signatures: list, threshold: float = 0.5) -> list:
    """Greedy threshold clustering; returns cluster-index per item."""
    reps: list[tuple] = []
    assign: list[int] = []
    for sig in signatures:
        for cid, rep in enumerate(reps):
            if estimated_jaccard(sig, rep) >= threshold:
                assign.append(cid)
                break
        else:
            reps.append(sig)
            assign.append(len(reps) - 1)
    return assign


def shannon(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return -sum((c / total) * math.log(c / total)
                for c in counter.values())


def trace_diversity(traces: list, threshold: float = 0.5) -> dict:
    """Frozen contract over a list of trace strings."""
    texts = [t for t in traces if (t or "").strip()]
    if not texts:
        return {"n_traces": 0, "n_clusters": 0,
                "cluster_entropy": 0.0, "pairwise_diversity": 0.0,
                "largest_cluster_frac": 0.0}
    sigs = [minhash_signature(t) for t in texts]
    assign = cluster(sigs, threshold)
    sizes = Counter(assign)
    n = len(texts)
    entropy = shannon(sizes) / math.log(len(sizes)) if len(sizes) > 1 \
        else 0.0
    pairs = [(i, j) for i in range(len(sizes))
             for j in range(i + 1, len(sizes))]
    if pairs:
        # representative = first signature of each cluster
        first: dict = {}
        for idx, cid in enumerate(assign):
            first.setdefault(cid, sigs[idx])
        import itertools
        sims = [estimated_jaccard(first[a], first[b])
                for a, b in itertools.combinations(sorted(first), 2)]
        diversity = 1.0 - (sum(sims) / len(sims))
    else:
        diversity = 0.0
    return {"n_traces": n, "n_clusters": len(sizes),
            "cluster_entropy": round(entropy, 4),
            "pairwise_diversity": round(diversity, 4),
            "largest_cluster_frac": round(max(sizes.values()) / n, 4)}
