"""Anchors for the audit chain. Immutable. Verbatim copy of the ATLAS
anchor; only the module path differs (gv.audit.chain, chain.py itself
is copied verbatim)."""
import pytest

from gv.audit.chain import AuditChain


def test_genesis_and_order():
    chain = AuditChain()
    chain.append({"action": "a"})
    chain.append({"action": "b"})
    ok, bad = chain.verify()
    assert ok and bad is None
    assert chain.entries[0]["prev"] == "0" * 64


def test_single_byte_flip_detected():
    chain = AuditChain()
    for i in range(10):
        chain.append({"action": f"a{i}"})
    chain.entries[5]["event"]["action"] = "tampered"
    ok, bad = chain.verify()
    assert not ok and bad in (5, 6)


def test_hash_omission_or_reorder_detected():
    chain = AuditChain()
    chain.append({"action": "x", "k": 1})
    del chain.entries[0]["hash"]
    ok, bad = chain.verify()
    assert not ok


def test_save_load_roundtrip(tmp_path):
    chain = AuditChain()
    chain.append({"action": "a"})
    chain.append({"action": "b"})
    p = tmp_path / "audit.jsonl"
    chain.save(p)
    loaded = AuditChain.load(p)
    assert loaded.verify() == (True, None)
    assert len(loaded.entries) == 2
