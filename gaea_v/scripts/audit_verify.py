"""audit_verify: walk logs/audit.jsonl and fail loud on tampering."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gv.audit.chain import AuditChain  # noqa: E402


def main() -> int:
    log = ROOT / "logs" / "audit.jsonl"
    if not log.exists():
        print(json.dumps({"log": str(log), "ok": False,
                          "reason": "chain missing"}))
        return 1
    chain = AuditChain.load(log)
    ok, bad = chain.verify()
    result = {"log": "logs/audit.jsonl",
              "entries": len(chain.entries), "ok": ok,
              "first_bad_seq": bad}
    print(json.dumps(result))
    if not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
