"""run_eval: una condición sobre la escalera (artefactos + manifiesto).

Conditions are measurement runs; inferential claims live only in
scripts/*_measured.py with the prereg loaded. Supported modes today:
nano and atlas (fp32). int8 rides the same bridge with bridge_mode
declared in the manifest when the heph side exposes it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gv.audit.chain import AuditChain  # noqa: E402
from gv.bridge.atlas_hook import AtlasHook  # noqa: E402
from gv.canon import config_sha256  # noqa: E402
from gv.harness.runner import run_condition  # noqa: E402
from gv.harness.task_ladder import load_ladder  # noqa: E402


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "nano"
    condition = f"eval_{mode}"
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    tasks = load_ladder(ROOT / "profiles")
    chain_path = ROOT / "logs" / "audit.jsonl"
    chain = AuditChain.load(chain_path) if chain_path.exists() \
        else AuditChain()
    hook = AtlasHook(config, ROOT)
    try:
        ident = hook.verify_identity(config)
        anchor = config["identities"]

        def solver(task: dict) -> dict:
            res = hook.solve(task, mode=mode,
                             budget=config["pilot"]["budget"],
                             max_iters=config["pilot"]["max_iters"])
            return {"tests_passed": bool(res["tests_passed"]),
                    "decision": res.get("decision"),
                    "nodes_evaluated": res.get("nodes_evaluated", 0),
                    "tokens_generated": res.get("tokens_generated", 0)}

        manifest = run_condition(
            condition, tasks, solver, ROOT / "artifacts" / "runs",
            config_sha256=config_sha256(ROOT / "config.yaml"),
            git_head="uncommitted", atlas_git_head=ident["git_head"],
            heph_binary_sha256=anchor["heph_binary_sha256"],
            weights_sha256=anchor["weights_sha256"],
            seed=config["seed"], bridge_mode="fp32",
            probe_status="desactivado",
            notes="measurement run; no inferential claim", chain=chain)
        chain.save(chain_path)
        print(json.dumps({"run_id": manifest["run_id"],
                          "accuracy_by_tier":
                          manifest["accuracy_by_tier"],
                          "suite_digest": manifest["suite_digest"]}))
        return 0
    finally:
        hook.close()


if __name__ == "__main__":
    raise SystemExit(main())
