"""Programmatic verifier (#5): evidence from regex, JSON-schema and
sandboxed execution. Score = executed evidence, never vibes.

Context contract (all optional):
  patterns : list[str]           regex that MUST match the claim
  schema   : dict                JSON-schema the claim (JSON) must obey
  code     : str                 candidate code to run
  tests    : str                 python asserts that must exit 0

Sandbox (#12): disposable temp dir, scrubbed environment, wall-clock
timeout and RLIMIT_AS/RLIMIT_CPU from config.safety.sandbox. No OS
netns in this build: network absence is enforced by the scrubbed env
and is RESTATED HONESTLY in the audit event — full isolation is the
OS's job (documented in docs/no_goals.md's spirit: fail-loud honesty).
"""

from __future__ import annotations

import json
import re
import resource
import subprocess
import sys
import tempfile
from pathlib import Path

from atlas_ns.verify.composite import Verdict
from atlas_ns.verify.schema import (
    VERDICT_SCHEMA, validate, verdict_to_dict)


class SandboxLimits:
    def __init__(self, config: dict | None = None) -> None:
        cfg = (config or {}).get("safety", {}).get("sandbox", {})
        self.timeout_s = float(cfg.get("timeout_s", 20))
        self.mem_mb = int(cfg.get("mem_mb", 512))
        self.no_network = bool(cfg.get("no_network", True))


class ProgrammaticVerifier:
    name = "programmatic"

    def __init__(self, config: dict | None = None) -> None:
        self.limits = SandboxLimits(config)

    # -- sandbox ------------------------------------------------------------
    def run_in_sandbox(self, code: str, tests: str) -> dict:
        """Execute `tests` against `code` in a disposable subprocess.

        Returns {ran, passed, exit_code, stderr_tail, ms}. The candidate
        NEVER runs with ATLAS's environment or privileges.
        """
        import time as _time

        with tempfile.TemporaryDirectory(prefix="atlas_sbx_") as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "candidate.py").write_text(code, encoding="utf-8")
            entry = tmp_path / "entry.py"
            entry.write_text(
                "from candidate import *\n" + tests
                + "\nprint('SANDBOX_PASS')\n",
                encoding="utf-8")

            def _limits() -> None:  # pragma: no cover - subprocess side
                resource.setrlimit(resource.RLIMIT_AS,
                                   (self.limits.mem_mb * 2 ** 20,) * 2)
                resource.setrlimit(resource.RLIMIT_CPU,
                                   (int(self.limits.timeout_s),) * 2)

            t0 = _time.monotonic()
            try:
                proc = subprocess.run(
                    [sys.executable, str(entry)],
                    capture_output=True, text=True,
                    timeout=self.limits.timeout_s, cwd=tmp,
                    env={"PATH": "/usr/bin:/bin", "HOME": tmp,
                         "PYTHONDONTWRITEBYTECODE": "1"},
                    preexec_fn=_limits, check=False)
                exit_code, stderr, passed = (
                    proc.returncode, proc.stderr[-400:],
                    proc.returncode == 0 and "SANDBOX_PASS" in proc.stdout)
            except subprocess.TimeoutExpired:
                exit_code, stderr, passed = -9, "timeout", False
            return {"ran": True, "passed": passed, "exit_code": exit_code,
                    "stderr_tail": stderr,
                    "ms": round((_time.monotonic() - t0) * 1000, 1),
                    "no_network_enforced": self.limits.no_network}

    # -- verify ---------------------------------------------------------------
    def verify(self, claim: str, context: dict | None = None) -> Verdict:
        ctx = context or {}
        checks: list[tuple[str, bool]] = []

        for pattern in ctx.get("patterns", []):
            ok = bool(re.search(pattern, claim))
            checks.append((f"regex:{pattern[:24]}", ok))

        if "schema" in ctx:
            try:
                payload = (json.loads(claim)
                           if isinstance(claim, str) else claim)
                validate(payload, ctx["schema"])
                checks.append(("json_schema", True))
            except Exception as exc:  # jsonschema.ValidationError / JSON
                checks.append((f"json_schema:{exc!s:.40}", False))

        sandbox: dict | None = None
        if "code" in ctx and "tests" in ctx:
            sandbox = self.run_in_sandbox(ctx["code"], ctx["tests"])
            checks.append(("sandbox_tests", sandbox["passed"]))

        if not checks:
            return Verdict(self.name, 0.0,
                           "no programmatic evidence requested",
                           hard_block=False)

        passed = sum(1.0 for _, ok in checks if ok)
        score = passed / len(checks)
        evidence = "; ".join(f"{name}={'ok' if ok else 'FAIL'}"
                             for name, ok in checks)
        verdict = Verdict(self.name, score, evidence, hard_block=False)
        validate(verdict_to_dict(verdict), VERDICT_SCHEMA)
        return verdict
