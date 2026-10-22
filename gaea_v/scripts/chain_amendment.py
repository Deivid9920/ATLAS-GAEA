"""Chain the atlas_git_head amendment (S-08) into logs/audit.jsonl.

Appends two events: the amendment record (from/to, cause, fix commit,
ATLAS suite result) and the re-hash of config.yaml after the edit.
Run AFTER config.yaml was edited and BEFORE any further measured run.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gv.audit.chain import AuditChain  # noqa: E402
from gv.canon import config_sha256  # noqa: E402


def main() -> int:
    chain_path = ROOT / "logs" / "audit.jsonl"
    chain = AuditChain.load(chain_path)
    ok, bad = chain.verify()
    if not ok:
        raise SystemExit(f"audit chain broken at seq {bad}; refusing")
    new_hash = config_sha256(ROOT / "config.yaml")
    chain.append({"action": "amendment_atlas_head",
                  "created_utc": datetime.now(timezone.utc).isoformat(
                      timespec="seconds"),
                  "from": "ecb494b", "to": "4427672",
                  "cause": "S-08 zoo malicious 0.00 (ZOO-401/402/403 "
                           "APPROVED); master prompt FASE 3.e mandates "
                           "fixing the verifier in ATLAS before FASE 5",
                  "fix": "atlas_ns/verify/plugins/policy.py @ atlas "
                         "commit 4427672; weight 0.0 hard-block",
                  "atlas_tests": "182/182",
                  "docs": "docs/ANCHOR_CHANGES.md",
                  "config_sha256": new_hash})
    chain.append({"action": "config_sha256_chained",
                  "config_sha256": new_hash})
    chain.save(chain_path)
    print(new_hash)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
