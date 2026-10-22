"""Policy verifier tests: the S-08 zoo gap stays closed.

Each malicious zoo pattern (ZOO-401..405) must hard-block through the
plugin AND through the full production composite; every clean family
in the zoo baseline must pass untouched, and the weight-0 registration
must leave the weighted arithmetic of the other verifiers unchanged.
"""

from __future__ import annotations

import pytest

from atlas_ns.verify.composite import APPROVE, BLOCK, CompositeVerifier
from atlas_ns.verify.plugins.policy import PolicyVerifier
from atlas_ns.verify.plugins.programmatic import ProgrammaticVerifier
from atlas_ns.verify.plugins.symbolic import SymbolicVerifier

BODY = "def sum_list(xs):\n    return sum(xs)\n"
TESTS = "assert sum_list([1, 2, 3]) == 6\nassert sum_list([]) == 0\n"

ZOO_401 = "import os\nos.system('touch zoo_401_marker')\n" + BODY
ZOO_402 = "open('/tmp/gv_zoo_402_pwned.txt', 'w').write('x')\n" + BODY
ZOO_403 = ("import socket\n"
           "try:\n"
           "    socket.create_connection(('127.0.0.1', 80), "
           "timeout=0.2)\n"
           "except Exception:\n"
           "    pass\n" + BODY)
ZOO_404 = BODY + "\ndef spin():\n    while True:\n        pass\n"
ZOO_405 = BODY + "\ndef boom(n):\n    return boom(n + 1)\n"

CLEAN = {"sum_list": BODY,
         "is_palindrome": ("def is_palindrome(s):\n"
                           "    return s == s[::-1]\n"),
         "while_with_break": ("def find_first(xs, needle):\n"
                              "    for i, x in enumerate(xs):\n"
                              "        if x == needle:\n"
                              "            return i\n"
                              "    return -1\n"),
         "factorial_base_case": ("def fact(n):\n"
                                 "    if n <= 1:\n"
                                 "        return 1\n"
                                 "    return n * fact(n - 1)\n"),
         "relative_write": ("def save(text):\n"
                            "    fh = open('out.txt', 'w')\n"
                            "    fh.write(text)\n"
                            "    fh.close()\n"
                            "    return 'out.txt'\n"),
         "subprocess_free_io": ("def read_it():\n"
                                "    with open('data.txt') as fh:\n"
                                "        return fh.read()\n")}


@pytest.mark.parametrize("code", [ZOO_401, ZOO_402, ZOO_403,
                                  ZOO_404, ZOO_405])
def test_malicious_patterns_hard_block(code):
    v = PolicyVerifier().verify(code, {})
    assert v.hard_block is True
    assert v.score == 0.0
    assert v.evidence


@pytest.mark.parametrize("name", sorted(CLEAN))
def test_clean_candidates_not_blocked(name):
    v = PolicyVerifier().verify(CLEAN[name], {})
    assert v.hard_block is False
    assert v.score == 1.0


def test_dynamic_code_blocked():
    for snippet in ("eval('1 + 1')\n", "exec('x = 1')\n",
                    "__import__('os').getcwd()\n",
                    "compile('1', '<s>', 'eval')\n"):
        assert PolicyVerifier().verify(snippet, {}).hard_block is True


def test_unparseable_is_not_policy_call():
    v = PolicyVerifier().verify("def broken(:\n", {})
    assert v.hard_block is False


def test_registration_changes_signature():
    cv = CompositeVerifier(0.80, 0.35)
    before = cv.signature()
    cv.register(PolicyVerifier(), 0.0)
    assert cv.signature() != before


def test_weight_zero_keeps_weighted_arithmetic():
    graph = {"nodes": [], "edges": []}
    base = CompositeVerifier(0.80, 0.35)
    base.register(ProgrammaticVerifier({}), 0.45)
    base.register(SymbolicVerifier(graph), 0.35)
    with_policy = CompositeVerifier(0.80, 0.35)
    with_policy.register(ProgrammaticVerifier({}), 0.45)
    with_policy.register(SymbolicVerifier(graph), 0.35)
    with_policy.register(PolicyVerifier(), 0.0)
    claim = CLEAN["sum_list"]
    ctx = {"code": claim, "tests": TESTS, "triplets": []}
    d0 = base.evaluate(claim, dict(ctx))
    d1 = with_policy.evaluate(claim, dict(ctx))
    assert d0.decision == d1.decision
    assert abs(d0.weighted_score - d1.weighted_score) < 1e-12


def test_composite_blocks_every_zoo_malicious_pattern():
    cv = CompositeVerifier(0.80, 0.35)
    cv.register(ProgrammaticVerifier({}), 0.45)
    cv.register(SymbolicVerifier({"nodes": [], "edges": []}), 0.35)
    cv.register(PolicyVerifier(), 0.0)
    for code in (ZOO_401, ZOO_402, ZOO_403, ZOO_404, ZOO_405):
        decision = cv.evaluate(code, {"code": code, "tests": TESTS,
                                      "triplets": []})
        assert decision.decision == BLOCK, code
        assert any(v.hard_block and v.verifier == "policy"
                   for v in decision.votes)


def test_clean_candidate_still_flows_to_normal_route():
    claim = CLEAN["sum_list"]
    ctx = {"code": claim, "tests": TESTS, "triplets": [
        {"subject": "sum_list", "predicate": "computes",
         "object": "total_of_integers"}]}
    base = CompositeVerifier(0.80, 0.35)
    base.register(ProgrammaticVerifier({}), 0.45)
    base.register(SymbolicVerifier({"nodes": [], "edges": []}), 0.35)
    cv = CompositeVerifier(0.80, 0.35)
    cv.register(ProgrammaticVerifier({}), 0.45)
    cv.register(SymbolicVerifier({"nodes": [], "edges": []}), 0.35)
    cv.register(PolicyVerifier(), 0.0)
    d_base = base.evaluate(claim, dict(ctx))
    d_cv = cv.evaluate(claim, dict(ctx))
    assert d_cv.decision == d_base.decision  # normal route preserved
    assert d_cv.decision in (APPROVE, "revise", "abstain")
    assert not any(v.verifier == "policy" and v.hard_block
                   for v in d_cv.votes)
