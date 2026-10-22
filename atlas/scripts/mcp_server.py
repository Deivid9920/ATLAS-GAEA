#!/usr/bin/env python3
"""MCP server (#21, FASE 1): minimal stdio JSON-RPC 2.0.

Exposes the composite verifier and the bridge AS TOOLS for external
agents:
  atlas.health   {}                          -> bridge receipt
  atlas.generate {prompt, max_new_tokens}    -> nano text (audited)
  atlas.verify   {claim, context?}           -> composite verdict

Every call is appended to logs/audit.jsonl via the tamper-evident
chain. stdio transport per config.bridge.mcp; no external deps (the
native `mcp` package is optional and not required by this fallback).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from atlas_ns.audit.chain import AuditChain
from atlas_ns.bridge.hephaestus import HephaestusBridge

METHODS = ("atlas.health", "atlas.generate", "atlas.verify")


def build(config: dict, root: Path) -> dict:
    """Wire the tool implementations once; the loop stays dumb."""
    bridge = HephaestusBridge(config, repo_root=root)

    # The composite verifier is registered by FASE 2 plugins; FASE 1
    # ships the honest placeholder that refuses to invent a verdict.
    def verify(claim: str, context: dict | None) -> dict:
        return {"decision": "abstain",
                "reason": "verifier plugins land in FASE 2; "
                          "atlas.verify refuses to fabricate verdicts",
                "claim": claim}

    impl = {
        "atlas.health": lambda params: bridge.health(),
        "atlas.generate": lambda params: bridge.generate(
            params.get("prompt", ""),
            int(params.get("max_new_tokens", 32))),
        "atlas.verify": lambda params: verify(
            params.get("claim", ""), params.get("context")),
    }
    return impl


def serve(config: dict, root: Path) -> None:  # pragma: no cover - REPL
    impl = build(config, root)
    chain = AuditChain()
    audit_path = root / "logs" / "audit.jsonl"
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        method = "?"
        req: dict = {}
        try:
            req = json.loads(line)
            method = req.get("method", "")
            if method not in METHODS:
                raise ValueError(f"unknown method {method!r}")
            result = impl[method](req.get("params") or {})
            chain.append({"action": "mcp_call", "method": method,
                          "params_hash": hash(json.dumps(
                              req.get("params") or {}, sort_keys=True)) % 10**8,
                          "ok": True})
            resp = {"jsonrpc": "2.0", "id": req.get("id"), "result": result}
        except Exception as exc:
            chain.append({"action": "mcp_call", "method": method,
                          "ok": False, "error": str(exc)[:200]})
            resp = {"jsonrpc": "2.0",
                    "id": req.get("id") if isinstance(req, dict) else None,
                    "error": {"code": -32603, "message": str(exc)[:300]}}
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        chain.save(audit_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    args = ap.parse_args()
    root = Path(args.config).resolve().parent
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    serve(config, root)


if __name__ == "__main__":
    main()
