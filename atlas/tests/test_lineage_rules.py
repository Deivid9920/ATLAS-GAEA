"""Anchors for the growth rule. Immutable."""
from atlas_ns.lineage.rules import (
    ExpansionMetrics, GrowthRules, MergeCandidate, decide_expansion,
    merge_decide)


R = GrowthRules(min_fail_rate=0.15, min_unrecovered_rate=0.05,
                diversity_floor=0.80, min_generations_between=3,
                ceiling_params=7.0e9)


def m(**kw):
    base = dict(fail_rate=0.30, unrecovered_rate=0.10, diversity_ratio=0.9,
                generations_since_growth=5, params_current=285e6,
                audit_ok=True)
    base.update(kw)
    return ExpansionMetrics(**base)


def test_growth_justified_by_saturation():
    d = decide_expansion(m(), R)
    assert d.expand and not d.causes


def test_refuses_when_not_saturated():
    d = decide_expansion(m(fail_rate=0.05), R)
    assert not d.expand and any(c.startswith("G1") for c in d.causes)


def test_refuses_when_search_recovers():
    d = decide_expansion(m(unrecovered_rate=0.01), R)
    assert not d.expand


def test_refuses_broken_diversity_or_audit():
    assert not decide_expansion(m(diversity_ratio=0.5), R).expand
    assert not decide_expansion(m(audit_ok=False), R).expand


def test_refuses_ceiling_and_pacing():
    assert not decide_expansion(m(params_current=8e9), R).expand
    assert not decide_expansion(m(generations_since_growth=1), R).expand


def test_merge_diversity_floor():
    c = [MergeCandidate("a", 0.9, "lin1"), MergeCandidate("b", 0.8, "lin1"),
         MergeCandidate("c", 0.7, "lin2")]
    picked, why = merge_decide(c, k=2)
    assert set(picked) == {"a", "c"}, why


def test_merge_trivial():
    assert merge_decide([], 3) == ([], "nothing to merge")
