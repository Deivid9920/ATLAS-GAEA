"""fase6_open: apertura con gate de FASE 5 y enmienda de esquema GAEA-L.

Fail-loud: refuses to open FASE 6 unless the FASE 5 evidence is on
disk (RFT round manifest, final inference, zoo v2 baseline), the audit
chain verifies end to end, and the sibling identities still match the
frozen anchors. Then it chains two events:
  fase6_started                    the phase gate is green
  manifest_schema_fields_reserved  the GAEA-L amendment (FASE 6.d),
                                   registered BEFORE any FASE 6 run
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yaml  # noqa: E402

from gv.audit.chain import AuditChain  # noqa: E402


def _git_head() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, cwd=str(ROOT))
    return out.stdout.strip() or "uncommitted"


def main() -> int:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    log = ROOT / "logs" / "audit.jsonl"
    chain = AuditChain.load(log)
    ok, bad = chain.verify()
    if not ok:
        print(json.dumps({"ok": False, "reason": f"chain broken at {bad}"}))
        return 1

    fase5_evidence = {
        "rft_round_manifest": ROOT / "artifacts" / "rft" / "round_1"
                              / "round_manifest.json",
        "rft_final_inference": ROOT / "artifacts" / "rft"
                               / "final_inference.json",
        "zoo_baseline": ROOT / "artifacts" / "zoo_baseline.json",
    }
    missing = [k for k, p in fase5_evidence.items() if not p.is_file()]
    if missing:
        print(json.dumps({"ok": False, "reason": "FASE 5 gate not green",
                          "missing": missing}))
        return 1

    head = _git_head()
    hook_state = subprocess.run(
        ["git", "-C", str(ROOT.parent / "atlas"), "rev-parse",
         "--short", "HEAD"], capture_output=True, text=True)
    atlas_head = hook_state.stdout.strip()
    if atlas_head != config["identities"]["atlas_git_head"]:
        print(json.dumps({"ok": False,
                          "reason": "atlas head drifted from anchor",
                          "atlas_head": atlas_head}))
        return 1

    events = [
        {"action": "fase6_started", "gate": "F-5 closed and measured",
         "gaea_v_head": head, "atlas_git_head": atlas_head,
         "chain_entries_before": len(chain.entries),
         "fase5_evidence": sorted(fase5_evidence)},
        {"action": "manifest_schema_fields_reserved",
         "fields": ["substrate_id", "matching_params",
                    "matching_training_flops"],
         "schema_version": "gv.manifest/1",
         "rule": "closed schema extended: all three fields mandatory in "
                 "new manifests; null when the condition is not a GAEA "
                 "substrate; params and flops always reported together",
         "amendment": "docs/ANCHOR_CHANGES.md 2026-10-21 GAEA-L",
         "registered": "before any FASE 6 run (no data seen)",
         "operator_authorization": "Continua con la FASE 6"},
    ]
    for ev in events:
        chain.append(ev)
    chain.save(log)
    print(json.dumps({"ok": True, "chained": [e["action"] for e in events],
                      "entries": len(chain.entries)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
