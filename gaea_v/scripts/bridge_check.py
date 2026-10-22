"""bridge_check: identity of the read-only bridge to ATLAS/HEPHAESTUS.

Fails loud when the ATLAS git head, the heph binary hash or the
champion weights hash drift from the frozen anchors.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gv.bridge.atlas_hook import AtlasHook, BridgeError  # noqa: E402


def main() -> int:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    hook = AtlasHook(config, ROOT)
    try:
        ident = hook.verify_identity(config)
        out = {"ok": True, "git_head": ident["git_head"],
               "binary_sha256": ident["binary_sha256"],
               "weights_sha256": ident["weights_sha256"]}
    except BridgeError as exc:
        out = {"ok": False, "error": str(exc)}
    finally:
        hook.close()
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "logs" / "bridge_check.json").write_text(
        json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
