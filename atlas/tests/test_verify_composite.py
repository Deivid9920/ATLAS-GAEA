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
