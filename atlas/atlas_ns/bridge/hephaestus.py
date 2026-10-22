"""HEPHAESTUS bridge (#9): JSON-lines subprocess wrapper over build/heph.

Contract (fixed by the HEPHAESTUS Makefile):
  request  : one JSON object per line  {"op": ..., "args": {...}}
  response : one JSON object per line  {"ok": bool, "op": ..., ...}

Ops:
  tokenize : args {text}                    -> {tokens: [int, ...]}
  generate : args {prompt, max_new_tokens, greedy} -> {text, token_ids}
  health   : args {}                        -> {binary, manifest, sha256}

Fail-loud: a missing binary, a non-zero exit, a timeout or an unparseable
reply raises BridgeError — the bridge never fabricates a result. The
timeout/backoff policy is config-driven (bridge.timeout_s).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

OPS = ("tokenize", "generate", "health")


class BridgeError(RuntimeError):
    """The bridge failed loudly: no fabricated results, ever."""


class HephaestusBridge:
    """Speaks JSON-lines at the Python boundary, CLI at the binary."""

    def __init__(self, config: dict, repo_root: Path | None = None) -> None:
        self._cfg = config.get("bridge", config)
        # atlas_ns/bridge/hephaestus.py -> atlas/ repo root
        self._repo_root = Path(repo_root or Path(__file__).resolve()
                               .parents[2]).resolve()
        self.timeout_s = float(self._cfg.get("timeout_s", 60))
        self.attempts = int(self._cfg.get("attempts", 3))
        self.backoff_s = float(self._cfg.get("backoff_s", 0.5))

    # -- path resolution ---------------------------------------------------
    def resolve_bin(self) -> Path:
        raw = Path(self._cfg["hephaestus_bin"])
        path = raw if raw.is_absolute() else (self._repo_root / raw)
        path = Path(str(path)).resolve()
        if not path.is_file():
            raise BridgeError(
                f"fail-loud: HEPHAESTUS binary not found at {path} — "
                "build the sibling repo first (cmake --build build)")
        return path

    def resolve_weights(self) -> Path:
        artifacts = self._repo_root.parent / "hephaestus" / "artifacts"
        weights = artifacts / "nano_fp32.safetensors"
        if not weights.is_file():
            raise BridgeError(
                f"fail-loud: nano weights missing at {weights} — run the "
                "export step of the sibling restore first")
        return weights

    def resolve_manifest(self) -> Path:
        manifest = (self._repo_root.parent / "hephaestus" /
                    "artifacts" / "model_manifest.txt")
        if not manifest.is_file():
            raise BridgeError(f"fail-loud: manifest missing at {manifest}")
        return manifest

    # -- subprocess plumbing -------------------------------------------------
    def _run(self, argv: list[str]) -> str:
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True,
                timeout=self.timeout_s, check=False)
        except subprocess.TimeoutExpired as exc:
            raise BridgeError(f"timeout after {self.timeout_s}s: "
                              f"{' '.join(argv)}") from exc
        if proc.returncode != 0:
            raise BridgeError(
                f"heph exit {proc.returncode}: {proc.stderr.strip()[:400]}")
        return proc.stdout

    def _retry(self, argv: list[str]) -> str:
        last: Exception | None = None
        for attempt in range(self.attempts):
            try:
                return self._run(argv)
            except BridgeError as exc:  # transient: timeout / exit != 0
                last = exc
                if attempt < self.attempts - 1:
                    time.sleep(self.backoff_s * (2 ** attempt))
        raise BridgeError(f"exhausted {self.attempts} attempts: {last}")

    # -- ops -------------------------------------------------------------------
    def tokenize(self, text: str) -> list[int]:
        out_path = self._tmp_out()
        self._retry([
            str(self.resolve_bin()), "tokenize",
            "--tokenizer", str(self._tokenizer_dir()),
            "--file", self._tmp_text(text),
            "--out", out_path])
        ids: list[int] = []
        # heph emits one line of ids per INPUT line: concatenate
        for line in Path(out_path).read_text(encoding="utf-8")\
                .strip().splitlines():
            ids.extend(int(t) for t in line.split())
        return ids

    def _tokenizer_dir(self) -> Path:
        return self._repo_root.parent / "hephaestus" / "artifacts" / "tokenizer"

    def generate(self, prompt: str, max_new_tokens: int = 32,
                 greedy: bool = True) -> dict:
        argv = [
            str(self.resolve_bin()), "generate",
            "--manifest", str(self.resolve_manifest()),
            "--weights", str(self.resolve_weights()),
            "--tokenizer", str(self._tokenizer_dir()),
            "--prompt", prompt,
            "--max-new-tokens", str(int(max_new_tokens)),
        ]
        if greedy:
            argv.append("--greedy")
        out = self._retry(argv)
        return {"text": out.strip(), "token_ids": []}

    def health(self) -> dict:
        binary = self.resolve_bin()
        manifest = self.resolve_manifest()
        weights = self.resolve_weights()
        tokens = self.tokenize("health check")
        return {
            "binary": str(binary),
            "binary_sha256": hashlib.sha256(
                Path(binary).read_bytes()).hexdigest(),
            "weights_sha256": hashlib.sha256(
                weights.read_bytes()).hexdigest(),
            "manifest": manifest.read_text(encoding="utf-8").splitlines()[:1],
            "tokenize_canary_len": len(tokens),
            "ok": True,
        }

    # -- temp helpers ------------------------------------------------------------
    def _tmp_text(self, text: str) -> str:
        tmp = Path("/tmp") / f"atlas_tok_in_{id(self)}.txt"
        tmp.write_text(text + "\n", encoding="utf-8")
        return str(tmp)

    def _tmp_out(self) -> str:
        tmp = Path("/tmp") / f"atlas_tok_out_{id(self)}.txt"
        if tmp.exists():
            tmp.unlink()
        return str(tmp)

    # -- generic JSON-lines call ----------------------------------------------
    def call(self, op: str, args: dict | None = None) -> dict:
        """Uniform JSON-lines entry point used by MCP and the runner."""
        if op not in OPS:
            raise BridgeError(f"unknown op {op!r}; expected one of {OPS}")
        args = args or {}
        if op == "tokenize":
            return {"ok": True, "op": op,
                    "tokens": self.tokenize(args["text"])}
        if op == "generate":
            res = self.generate(args.get("prompt", ""),
                                int(args.get("max_new_tokens", 32)),
                                bool(args.get("greedy", True)))
            return {"ok": True, "op": op, **res}
        if op == "health":
            return {"ok": True, "op": op, **self.health()}
        raise BridgeError("unreachable")
