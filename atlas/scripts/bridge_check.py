#!/usr/bin/env python3
"""bridge-check: resolve and certify the HEPHAESTUS bridge (hard gate).

Verifies, in order: binary exists -> manifest parses -> weights exist ->
tokenize canary returns ids -> generate returns text. Writes a JSON
receipt to logs/bridge_check.json. Exit 0 only if every step passed:
make demo refuses to run without this gate.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from atlas_ns.bridge.hephaestus import BridgeError, HephaestusBridge


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()

    root = Path(args.config).resolve().parent
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    receipt: dict = {"config": str(args.config), "steps": []}

    def step(name: str, fn):
        t0 = time.monotonic()
        try:
            detail = fn()
            receipt["steps"].append({"step": name, "ok": True,
                                     "ms": round((time.monotonic() - t0) * 1000,
                                                 1), "detail": detail})
            print(f"  ok  {name}: {detail}")
            return True
        except Exception as exc:  # fail-loud, but as a receipt
            receipt["steps"].append({"step": name, "ok": False,
                                     "ms": round((time.monotonic() - t0) * 1000,
                                                 1), "error": str(exc)})
            print(f"  FAIL {name}: {exc}")
            return False

    bridge = HephaestusBridge(config, repo_root=root)
    ok = True
    ok &= step("resolve_binary", lambda: str(bridge.resolve_bin()))
    ok &= step("resolve_weights", lambda: str(bridge.resolve_weights()))
    ok &= step("health", lambda: bridge.health())
    ok &= step("tokenize_canary",
               lambda: {"n_tokens": len(bridge.tokenize("bridge check"))})
    ok &= step("generate_smoke", lambda: {
        "prompt": "The meaning of",
        "text": bridge.generate("The meaning of", 8)["text"][:80]})

    receipt["ok"] = bool(ok)
    out = root / "logs" / "bridge_check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"receipt: {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
