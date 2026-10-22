#!/usr/bin/env python3
"""CLI: --logs logs/audit.jsonl; chain.verify() exit code.

Exit 0 = the chain is intact (compliance receipt valid); exit 1 =
tampering detected or the file is unreadable. The receipt is printed
as JSON for the audit trail.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from atlas_ns.audit.chain import AuditChain


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs/audit.jsonl")
    args = ap.parse_args()
    path = Path(args.logs)
    if not path.is_file():
        print(json.dumps({"log": str(path), "exists": False,
                          "ok": False,
                          "reason": "audit log not found"}))
        return 1
    chain = AuditChain.load(path)
    ok, bad = chain.verify()
    print(json.dumps({"log": str(path), "entries": len(chain.entries),
                      "ok": ok, "first_bad_seq": bad}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
