"""Anchors for the composite verifier. Immutable."""
import pytest

from atlas_ns.verify.composite import (
    ABSTAIN, APPROVE, BLOCK, REVISE, CompositeVerifier, Verdict)


class Fake:
    def __init__(self, name, score, hard_block=False, evidence=""):
        self.name, self._s, self._hb, self._e = name, score, hard_block, evidence

    def verify(self, claim, context):
        return Verdict(self.name, self._s, self._e, self._hb)


def make(progs=0.9, sym=0.9, probe=0.9):
    cv = CompositeVerifier(tau_approve=0.80, tau_doubt=0.35)
    cv.register(Fake("programmatic", progs), 0.45)
    cv.register(Fake("symbolic", sym), 0.35)
    cv.register(Fake("probe", probe), 0.20)
    return cv


def test_approve_on_consensus():
    assert make().evaluate("x").decision == APPROVE


def test_block_overrides_everything():
    cv = make(probe=0.99)
    cv._plugins[2]._hb = True
    d = cv.evaluate("x")
    assert d.decision == BLOCK and "symbolic" not in d.causes[0]


def test_all_doubt_abstains():
    assert make(progs=0.2, sym=0.1, probe=0.2).evaluate("x").decision == ABSTAIN


def test_partial_doubt_revises():
    d = make(progs=0.9, sym=0.1, probe=0.2).evaluate("x")
    assert d.decision == REVISE


def test_weighting_math():
    d = make(progs=1.0, sym=0.0, probe=0.0).evaluate("x")
    assert d.weighted_score == pytest.approx(0.45 / 1.0)


def test_signature_invalidates_cache():
    cv = make()
    cache = {}
    d1 = cv.evaluate_cached("q", {}, cache)
    d2 = cv.evaluate_cached("q", {}, cache)
    assert d1 is d2
    cv.register(Fake("extra", 1.0), 0.5)
    d3 = cv.evaluate_cached("q", {}, cache)
    assert d3 is not d1  # signature changed


def test_empty_registry_and_bad_taus():
    with pytest.raises(RuntimeError):
        CompositeVerifier(0.8, 0.3).evaluate("x")
    with pytest.raises(ValueError):
        CompositeVerifier(0.3, 0.8)


# -- v1.0.2 higiene: fronteras de pesos (ANCHOR_CHANGES #10) -----------------

def test_register_rejects_negative_weight():
    cv = CompositeVerifier()
    with pytest.raises(ValueError):
        cv.register(Fake("x", 0.9), -0.1)


def test_register_rejects_nonfinite_weight():
    cv = CompositeVerifier()
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            cv.register(Fake("x", 0.9), bad)


def test_zero_weight_vote_allowed_and_inert():
    # S-08: policy votes hard-block with weight 0.0. Register must ACCEPT
    # weight 0 and the weighted arithmetic of the others stays intact.
    cv = CompositeVerifier(tau_approve=0.80, tau_doubt=0.35)
    cv.register(Fake("programmatic", 0.9), 0.45)
    cv.register(Fake("policy", 1.0), 0.0)
    d = cv.evaluate("x")
    assert d.weighted_score == pytest.approx(0.9)  # 0.45*0.9 / 0.45
    cv._plugins[1]._hb = True
    assert cv.evaluate("x").decision == BLOCK


def test_evaluate_rejects_degenerate_registry():
    cv = CompositeVerifier()
    cv.register(Fake("a", 0.9), 0.0)
    cv.register(Fake("b", 0.9), 0.0)
    with pytest.raises(ValueError):
        cv.evaluate("x")
