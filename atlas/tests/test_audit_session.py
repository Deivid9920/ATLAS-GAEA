"""FASE 1: the audit chain is the compliance receipt.

Spec: chain.verify() True after 50 chained events and False after one
flipped byte — here exercised through a realistic bridge+permission
session.
"""
from pathlib import Path

from atlas_ns.audit.chain import AuditChain
from atlas_ns.safety.fencing import fence
from atlas_ns.safety.permissions import PermissionTable


def build_session_chain() -> AuditChain:
    chain = AuditChain()
    table = PermissionTable({"hephaestus": "execute",
                             "filesystem": "write"})
    for i in range(10):
        event = table.require("hephaestus", "execute")
        chain.append({"action": "bridge_call", "op": "generate",
                      "inputs_hash": f"h{i}", "verdict": None,
                      "permission": event})
        chain.append({"action": "fence_applied",
                      "fenced": fence(f"tool output {i}")[:32],
                      "verdict": None})
        chain.append({"action": "verifier_decision", "decision": "approve",
                      "inputs_hash": f"h{i}", "verdict": "approve",
                      "causes": ["programmatic: 0.900",
                                 "symbolic: 0.900",
                                 "probe: 0.900"]})
        chain.append({"action": "permission_check", "tool": "filesystem",
                      "needed": "write", "allowed": True})
        chain.append({"action": "task_commit", "task": f"t{i}",
                      "verdict": "committed"})
    return chain


def test_chain_verify_true_after_50_events():
    chain = build_session_chain()
    assert len(chain.entries) == 50
    ok, bad = chain.verify()
    assert ok is True and bad is None


def test_chain_verify_false_after_one_flipped_byte():
    chain = build_session_chain()
    entry = chain.entries[23]
    entry["event"]["action"] = entry["event"]["action"] + "x"  # 1-byte flip
    ok, bad = chain.verify()
    assert ok is False and bad in (23, 24)


def test_chain_survives_roundtrip_then_detects_tamper(tmp_path):
    chain = build_session_chain()
    p = tmp_path / "audit.jsonl"
    chain.save(p)
    loaded = AuditChain.load(p)
    assert loaded.verify() == (True, None)
    loaded.entries[0]["event"]["action"] = "rewritten"
    assert loaded.verify()[0] is False
