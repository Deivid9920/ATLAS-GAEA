"""scaffold: verifica el arbol declarado contra el disco.

Kept as the standing tree verifier: same contract as the structure
anchor, usable from the shell before packaging (M-01 countermeasure:
package_release refuses to ship a tree that fails this check).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "Makefile", "README.md", "config.yaml", "requirements.txt",
    "no_goals.md", "gv", "gv/audit/chain.py", "gv/stats/stats_core.py",
    "gv/stats/prereg.py", "gv/harness/runner.py",
    "gv/harness/task_ladder.py", "gv/harness/efficiency_manifest.py",
    "gv/contamination/fingerprints.py", "gv/contamination/gates.py",
    "gv/zoo/registry.py", "gv/probe/calibration.py",
    "gv/probe/cassandra_bridge.py", "gv/bridge/atlas_hook.py",
    "gv/bridge/policy_contract.py", "gv/lin/matching.py",
    "profiles/code_qa", "profiles/finance_docs", "docs",
    "artifacts/prereg", "artifacts/runs", "logs", "scripts", "tests",
]


def main() -> int:
    missing = [rel for rel in REQUIRED
               if not (ROOT / rel).exists()]
    if missing:
        print("missing:", missing)
        return 1
    print(f"tree ok ({len(REQUIRED)} entries present)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
