"""Anchor 14: prereg — family declared BEFORE data; the hash excludes
created_utc; editing the family after emission breaks verification."""
import json

import pytest

from gv.audit.chain import AuditChain
from gv.stats.prereg import (emit_prereg, prereg_hash, validate_prereg,
                             verify_prereg_file)

_PREREG = {
    "prereg_id": "prereg_test_pilot",
    "suite_digest": "d" * 64,
    "config_sha256": "c" * 64,
    "champion_tag_sha256": "t" * 64,
    "pilot_usage": "variance_only",
    "epsilon_equivalence": 0.15,
    "epsilon_derivation": {"n": 100, "variance_pilot": 0.25,
                           "power_target": 0.80, "method": "simulation",
                           "seed": 42},
    "family_hypotheses": [
        {"id": "H1", "claim": "atlas > nano_solo (accuracy)",
         "test": "paired_bootstrap", "direction": "superiority"},
        {"id": "H2", "claim": "acuerdo int8 == fp32",
         "test": "tost_equivalence", "direction": "equivalence"}],
    "claim_rule": "p_holm<0.05 AND ci_excludes_0; TOST inside epsilon",
    "excluded_patterns_contamination": [],
    "interim_monitoring": "allowed, no claims",
}


def test_hash_excludes_created_utc():
    a = dict(_PREREG, created_utc="2026-01-01T00:00:00+00:00")
    b = dict(_PREREG, created_utc="2030-12-31T23:59:59+00:00")
    assert prereg_hash(a) == prereg_hash(b)


def test_validation_guards():
    validate_prereg(_PREREG)
    with pytest.raises(ValueError):
        validate_prereg(dict(_PREREG, pilot_usage="both"))
    with pytest.raises(ValueError):
        validate_prereg(dict(_PREREG, epsilon_equivalence=-1))
    dup = dict(_PREREG, family_hypotheses=[
        _PREREG["family_hypotheses"][0],
        _PREREG["family_hypotheses"][0]])
    with pytest.raises(ValueError):
        validate_prereg(dup)


def test_emit_chains_and_verify(tmp_path):
    chain = AuditChain()
    path, digest = emit_prereg(_PREREG, chain, tmp_path)
    assert path.exists()
    data = json.loads(path.read_text())
    assert "created_utc" in data
    assert digest == prereg_hash(data)
    assert chain.entries[-1]["event"]["prereg_sha256"] == digest
    # verify outside the repo chain: no chained event found -> False
    assert verify_prereg_file(path) is False


def test_family_edit_breaks_hash(tmp_path):
    chain = AuditChain()
    path, digest = emit_prereg(_PREREG, chain, tmp_path)
    data = json.loads(path.read_text())
    tampered = dict(data, epsilon_equivalence=0.05)
    assert prereg_hash(tampered) != digest


def test_double_emit_refused(tmp_path):
    chain = AuditChain()
    emit_prereg(_PREREG, chain, tmp_path)
    with pytest.raises(FileExistsError):
        emit_prereg(_PREREG, chain, tmp_path)
