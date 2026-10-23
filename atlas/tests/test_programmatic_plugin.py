"""FASE 2: programmatic plugin — regex, JSON-schema, sandboxed tests.
Lote 2 (v1.1.0): el sandbox reporta el aislamiento REAL (no solo el
pedido) y puede exigir netns fail-closed. Tests = especificación.
"""
import sys

import pytest

import atlas_ns.verify.plugins.programmatic as prog_mod
from atlas_ns.verify.plugins.programmatic import (
    IsolationUnavailableError, ProgrammaticVerifier)

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


def test_sandbox_reports_enforcement_honestly(verifier):
    # v1.1.0 (ANCHOR_CHANGES #14): el resultado dice qué se PIDIÓ y qué se
    # CUMPLIÓ. Con isolation "none" (default) la red NO queda bloqueada a
    # nivel OS y el campo lo dice sin maquillaje.
    res = verifier.run_in_sandbox("x = 1", "assert x == 1")
    assert res["isolation_profile"] == "subprocess+rlimits"
    assert res["no_network_requested"] is True   # config default
    assert res["no_network_enforced"] is False   # realidad, no deseo


def test_netns_requested_without_capability_fails_closed(monkeypatch):
    # fail-closed: si se pide netns y el host no puede crearlo, el verificador
    # SE NIEGA a lanzar el hijo — nunca corre con red "por si acaso".
    monkeypatch.setattr(prog_mod, "_netns_available", lambda: False)
    v = ProgrammaticVerifier({"safety": {"sandbox": {
        "no_network": True, "isolation": "netns"}}})
    with pytest.raises(IsolationUnavailableError) as ei:
        v.run_in_sandbox("x = 1", "assert x == 1")
    assert "unshare" in str(ei.value) and "netns" in str(ei.value)


def test_netns_available_wraps_child_with_unshare(monkeypatch):
    # con capacidad real, el hijo se lanza bajo `unshare --net` y el resultado
    # declara enforcement verificado.
    calls = {}

    class _FakeProc:
        returncode, stdout, stderr = 0, "SANDBOX_PASS", ""

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return _FakeProc()

    monkeypatch.setattr(prog_mod, "_netns_available", lambda: True)
    monkeypatch.setattr(prog_mod.subprocess, "run", fake_run)
    v = ProgrammaticVerifier({"safety": {"sandbox": {
        "no_network": True, "isolation": "netns"}}})
    res = v.run_in_sandbox("x = 1", "assert x == 1")
    assert calls["cmd"][0].endswith("unshare")
    assert calls["cmd"][1] == "--net"
    assert calls["cmd"][2].endswith("python" + ("3" if sys.version_info[0] == 3 else "")) or sys.executable in calls["cmd"][2]
    assert res["no_network_enforced"] is True
    assert res["isolation_profile"] == "subprocess+rlimits+netns"


def test_last_sandbox_recorded_for_audit_piping():
    # el runner (ANCHOR_CHANGES #15) lee last_sandbox para el evento de
    # auditoría; el verificador lo deja actualizado tras cada corrida.
    # (instancia fresca: la fixture del módulo ya corrió sandboxes antes)
    fresh = ProgrammaticVerifier()
    assert fresh.last_sandbox is None
    fresh.run_in_sandbox("x = 1", "assert x == 1")
    assert fresh.last_sandbox is not None
    assert fresh.last_sandbox["isolation_profile"] == "subprocess+rlimits"


def test_no_evidence_is_zero_not_fake(verifier):
    v = verifier.verify("anything", {})
    assert v.score == 0.0 and "no programmatic evidence" in v.evidence


def test_verdict_schema_valid(verifier):
    from atlas_ns.verify.schema import VERDICT_SCHEMA, validate, verdict_to_dict
    v = verifier.verify("x", {"patterns": ["."]})
    validate(verdict_to_dict(v), VERDICT_SCHEMA)  # must not raise
