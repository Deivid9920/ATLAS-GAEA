"""fase6_contract: congelar policy_contract v1 como GAEA-ready (FASE 6.c).

Runs the conformance check over a deterministic REFERENCE substrate
(a declared stub, not a trained model), freezes the result together
with the module hash into artifacts/policy_contract_v1.json, and
chains the freeze in the audit log. A future substrate (Mamba-2,
hybrid) that implements the three ops conforms by the same check and
enters the harness without arnes changes.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gv.audit.chain import AuditChain  # noqa: E402
from gv.bridge.policy_contract import (CONTRACT_VERSION,  # noqa: E402
                                       PolicyContractError,
                                       conformance_check)
from gv.canon import canonical, sha256_canonical, sha256_file  # noqa: E402

MODULE = ROOT / "gv" / "bridge" / "policy_contract.py"


class ReferenceSubstrate:
    """Deterministic contract stub: the minimal GAEA-ready surface."""

    def __init__(self, substrate_id: str = "reference_stub") -> None:
        self.substrate_id = substrate_id

    def __call__(self, request: dict) -> dict:
        op = request["op"]
        if op == "health":
            return {"ok": True, "substrate_id": self.substrate_id,
                    "contract_version": CONTRACT_VERSION}
        if op == "propose":
            n = int(request["args"]["n"])
            return {"ok": True,
                    "candidates": [{"token": f"c{i}"} for i in range(n)]}
        if op == "score":
            cand = request["args"]["candidate"]
            return {"ok": True, "score": 0.0,
                    "components": {"prior": 0.0,
                                   "token": str(cand.get("token"))}}
        raise PolicyContractError(f"unknown op {op!r}")


def main() -> int:
    out = ROOT / "artifacts" / "policy_contract_v1.json"
    if out.is_file():
        print(json.dumps({"ok": True, "skipped": "frozen artifact exists",
                          "path": str(out)}))
        return 0
    result = conformance_check(ReferenceSubstrate())
    artifact = {
        "contract_version": CONTRACT_VERSION,
        "module_sha256": sha256_file(MODULE),
        "ops": {
            "propose": {"request": {"op": "propose",
                                    "args": {"state": "...", "n": "int"}},
                        "response": {"ok": True, "candidates": "[...]"}},
            "score": {"request": {"op": "score",
                                  "args": {"candidate": "..."}},
                      "response": {"ok": True, "score": "float",
                                   "components": "{...}"}},
            "health": {"request": {"op": "health", "args": {}},
                       "response": {"ok": True, "substrate_id": "str",
                                    "contract_version": CONTRACT_VERSION}},
        },
        "conformance": dict(result, substrate_kind="reference_stub",
                            note="declared deterministic stub, not a "
                                 "trained substrate"),
        "frozen_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "gaea_ready_rule": "any substrate implementing exactly these "
                           "ops enters the bench without harness "
                           "changes; no tensor or weight crosses the "
                           "frontier",
    }
    artifact["artifact_sha256"] = sha256_canonical(
        {k: v for k, v in artifact.items() if k != "artifact_sha256"})
    out.write_text(canonical(artifact) + "\n", encoding="utf-8")

    log = ROOT / "logs" / "audit.jsonl"
    chain = AuditChain.load(log)
    ok, bad = chain.verify()
    if not ok:
        print(json.dumps({"ok": False, "reason": f"chain broken at {bad}"}))
        return 1
    chain.append({"action": "policy_contract_frozen",
                  "contract_version": CONTRACT_VERSION,
                  "module_sha256": artifact["module_sha256"],
                  "artifact_sha256": artifact["artifact_sha256"],
                  "conformance": result,
                  "phase": "FASE 6.c"})
    chain.save(log)
    print(json.dumps({"ok": True, "frozen": str(out),
                      "module_sha256": artifact["module_sha256"][:12],
                      "entries": len(chain.entries)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
