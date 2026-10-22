"""Lineage growth rules. Immutable anchor.

Growth (merge/expand) is ONLY justified when the verifier saturates:
G1 capacity, G2 integrity, G3 pacing, G4 ceiling. A refusal is the
system working — report it, never patch around it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExpansionMetrics:
    fail_rate: float
    unrecovered_rate: float
    diversity_ratio: float
    generations_since_growth: int
    params_current: int
    audit_ok: bool


@dataclass(frozen=True)
class GrowthRules:
    min_fail_rate: float
    min_unrecovered_rate: float
    diversity_floor: float
    min_generations_between: int
    ceiling_params: float


@dataclass(frozen=True)
class GrowthDecision:
    expand: bool
    causes: tuple[str, ...]
    checks: dict = field(default_factory=dict)


def decide_expansion(metrics: ExpansionMetrics,
                     rules: GrowthRules) -> GrowthDecision:
    """Apply G1-G4; every gate appends a human-readable cause on fail."""
    checks, causes = {}, []

    g1 = (metrics.fail_rate >= rules.min_fail_rate
          and metrics.unrecovered_rate >= rules.min_unrecovered_rate)
    checks["G1_saturation"] = {
        "fail_rate": metrics.fail_rate,
        "min_fail_rate": rules.min_fail_rate,
        "unrecovered_rate": metrics.unrecovered_rate,
        "min_unrecovered_rate": rules.min_unrecovered_rate, "pass": g1}
    if g1 is False:
        causes.append(
            "G1: capacity not saturated (fail rate or unrecovered rate "
            "below threshold): growth is not justified by the verifier")

    g2 = (metrics.diversity_ratio >= rules.diversity_floor
          and metrics.audit_ok)
    checks["G2_integrity"] = {"diversity": metrics.diversity_ratio,
                              "floor": rules.diversity_floor,
                              "audit_ok": metrics.audit_ok, "pass": g2}
    if g2 is False:
        causes.append("G2: integrity gate failed (diversity floor or "
                      "audit chain): fix the pipeline before growing")

    g3 = metrics.generations_since_growth >= rules.min_generations_between
    checks["G3_pacing"] = {"since": metrics.generations_since_growth,
                           "min": rules.min_generations_between,
                           "pass": g3}
    if g3 is False:
        causes.append("G3: pacing (too soon since last growth)")

    g4 = metrics.params_current < rules.ceiling_params
    checks["G4_ceiling"] = {"params": metrics.params_current,
                            "ceiling": rules.ceiling_params, "pass": g4}
    if g4 is False:
        causes.append("G4: parameter ceiling reached: grow capability, "
                      "not size (verifiers, profiles, search)")

    return GrowthDecision(all([g1, g2, g3, g4]), tuple(causes), checks)


@dataclass(frozen=True)
class MergeCandidate:
    name: str
    fitness: float
    diversity_id: str


def merge_decide(candidates: list[MergeCandidate], k: int,
                 min_pairwise_distinct: int = 2) -> tuple[list[str], str]:
    """Greedy fitness selection with a diversity floor: a candidate is
    skipped if fewer than min_pairwise_distinct distinct diversity_ids
    would remain among the picked set's neighbours. Deterministic order
    by (-fitness, name)."""
    if k <= 0 or not candidates:
        return [], "nothing to merge"
    ordered = sorted(candidates, key=lambda c: (-c.fitness, c.name))
    picked: list[MergeCandidate] = []
    for cand in ordered:
        if len(picked) >= k:
            break
        if len({c.diversity_id for c in picked}) < min_pairwise_distinct \
                and picked and cand.diversity_id == picked[-1].diversity_id \
                and len(candidates) - len(picked) >= k - len(picked):
            continue
        picked.append(cand)
    if len({c.diversity_id for c in picked}) < min(min_pairwise_distinct,
                                                   len(picked) or 1) \
            and len(picked) > 1:
        return [c.name for c in picked[:1]], \
            "diversity floor refused the merge: monoculture risk"
    return [c.name for c in picked], "fitness-ordered with diversity floor"
