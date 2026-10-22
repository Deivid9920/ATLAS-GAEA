"""FASE 2: programmatic plugin — regex, JSON-schema, sandboxed tests."""
import pytest

from atlas_ns.verify.plugins.programmatic import ProgrammaticVerifier

GOOD_CODE = """
def merge(a, b):
    out = []
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            out.append(a[i]); i += 1
        else:
            out.append(b[j]); j += 1
    return out + a[i:] + b[j:]
"""

GOOD_TESTS = """
assert merge([1, 3, 5], [2, 4]) == [1, 2, 3, 4, 5]
assert merge([], [1]) == [1]
print('extra-ok')
"""

BAD_TESTS = "assert merge([1, 3], [2]) == [99, 98]"  # genuinely wrong


@pytest.fixture(scope="module")
def verifier():
    return ProgrammaticVerifier()


def test_regex_rules(verifier):
    v = verifier.verify(
        "def merge(a, b): ...",
        {"patterns": [r"def merge", r"\ba\b"]})
    assert v.score == 1.0 and "ok" in v.evidence


def test_regex_fail_lowers_score(verifier):
    v = verifier.verify("def other(): ...", {"patterns": [r"def merge"]})
    assert v.score == 0.0 and "FAIL" in v.evidence


def test_json_schema_pass_and_fail(verifier):
    schema = {"type": "object",
              "required": ["answer"],
              "properties": {"answer": {"type": "string"}}}
    ok = verifier.verify('{"answer": "two-pointer scan"}',
                         {"schema": schema})
    bad = verifier.verify('{"answer": 42}', {"schema": schema})
    assert ok.score == 1.0 and bad.score == 0.0


def test_sandbox_executes_real_tests(verifier):
    res = verifier.verify("candidate", {"code": GOOD_CODE,
                                        "tests": GOOD_TESTS})
    assert res.score == 1.0 and "sandbox_tests=ok" in res.evidence


def test_sandbox_catches_failing_tests(verifier):
    res = verifier.verify("candidate", {"code": GOOD_CODE,
                                        "tests": BAD_TESTS})
    assert res.score == 0.0 and "sandbox_tests=FAIL" in res.evidence


def test_sandbox_timeout_is_bounded(verifier):
    res = verifier.run_in_sandbox("x = 1", "import time\ntime.sleep(30)")
    assert res["passed"] is False and res["exit_code"] == -9


def test_no_evidence_is_zero_not_fake(verifier):
    v = verifier.verify("anything", {})
    assert v.score == 0.0 and "no programmatic evidence" in v.evidence


def test_verdict_schema_valid(verifier):
    from atlas_ns.verify.schema import VERDICT_SCHEMA, validate, verdict_to_dict
    v = verifier.verify("x", {"patterns": ["."]})
    validate(verdict_to_dict(v), VERDICT_SCHEMA)  # must not raise
