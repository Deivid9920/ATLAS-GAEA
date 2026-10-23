"""Programmatic verifier (#5): evidence from regex, JSON-schema and
sandboxed execution. Score = executed evidence, never vibes.

Context contract (all optional):
  patterns : list[str]           regex that MUST match the claim
  schema   : dict                JSON-schema the claim (JSON) must obey
  code     : str                 candidate code to run
  tests    : str                 python asserts that must exit 0

Sandbox (#12 + Lote 2 v1.1.0, ANCHOR_CHANGES #14): disposable temp dir,
scrubbed environment, wall-clock timeout and RLIMIT_AS/RLIMIT_CPU from
config.safety.sandbox. El resultado reporta el perfil de aislamiento
REAL, no el deseado:
  isolation "none" (default) -> "subprocess+rlimits": el hijo corre como
      el MISMO usuario y PUEDE alcanzar la red; no_network_enforced=False.
  isolation "netns"          -> el hijo corre bajo `unshare --net`: sin
      red a nivel OS; no_network_enforced=True. Fail-CLOSED: si el host
      no puede crear el namespace, el verificador levanta
      IsolationUnavailableError ANTES de lanzar el hijo — jamás corre
      con red "por si acaso". Requiere WSL2/Linux con user namespaces.
El runner conecta {isolation_profile, no_network_requested,
no_network_enforced} al evento verifier_decision de la cadena
(ANCHOR_CHANGES #15): la auditoría dice siempre qué se enforzó de
verdad. `last_sandbox` guarda el perfil del ÚLTIMO sandbox ejecutado
por esta instancia del plugin (no por decisión).
Honesty rules: fail-loud, never fake a security property we do not
have. POSIX-only (resource/preexec_fn): on Windows this module fails
at import with guidance, never silently.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if os.name == "nt":  # pragma: no cover - platform guard
    raise RuntimeError(
        "sandbox POSIX-only: 'resource'/preexec_fn no existen en Windows. "
        "Ejecuta ATLAS bajo WSL2 o Linux (fail-loud con causa, no un "
        "ImportError opaco).")

import resource

from atlas_ns.verify.composite import Verdict
from atlas_ns.verify.schema import (
    VERDICT_SCHEMA, validate, verdict_to_dict)


class SandboxLimits:
    def __init__(self, config: dict | None = None) -> None:
        cfg = (config or {}).get("safety", {}).get("sandbox", {})
        self.timeout_s = float(cfg.get("timeout_s", 20))
        self.mem_mb = int(cfg.get("mem_mb", 512))
        self.no_network = bool(cfg.get("no_network", True))
        self.isolation = str(cfg.get("isolation", "none"))
        if self.isolation not in ("none", "netns"):
            raise ValueError(
                f"safety.sandbox.isolation inválido: {self.isolation!r} "
                "(valores: 'none' | 'netns')")


class IsolationUnavailableError(RuntimeError):
    """no_network+netns pedidos y el host no puede garantizarlos.
    Fail-closed: no se lanza el hijo."""


_netns_cache: bool | None = None


def _unshare_bin() -> str:
    import shutil

    return shutil.which("unshare") or "unshare"


def _netns_available() -> bool:
    """Probe real (una vez por proceso): `unshare --net true` debe
    terminar con exit 0. Sin root ni userns, devuelve False y el modo
    netns queda fail-closed."""
    global _netns_cache
    if _netns_cache is None:
        try:
            proc = subprocess.run(
                [_unshare_bin(), "--net", "true"],
                capture_output=True, timeout=10, check=False)
            _netns_cache = proc.returncode == 0
        except (OSError, subprocess.SubprocessError):
            _netns_cache = False
    return _netns_cache


class ProgrammaticVerifier:
    name = "programmatic"

    def __init__(self, config: dict | None = None) -> None:
        self.limits = SandboxLimits(config)
        self.last_sandbox: dict | None = None

    # -- sandbox ------------------------------------------------------------
    def run_in_sandbox(self, code: str, tests: str) -> dict:
        """Execute `tests` against `code` in a disposable subprocess.

        Returns {ran, passed, exit_code, stderr_tail, ms,
        no_network_requested, no_network_enforced, isolation_profile}.
        The candidate NEVER runs with ATLAS's environment or privileges.
        Fail-closed con netns: sin capacidad real se levanta
        IsolationUnavailableError antes de crear nada.
        """
        import time as _time

        want_netns = (self.limits.no_network
                      and self.limits.isolation == "netns")
        if want_netns and not _netns_available():
            raise IsolationUnavailableError(
                "no_network + isolation='netns' pedidos, pero este host no "
                "puede crear un network namespace (unshare --net falló o no "
                "está disponible). Ejecuta bajo WSL2/Linux con user "
                "namespaces, o declara isolation: 'none' si aceptas "
                "subprocess+rlimits SIN bloqueo real de red.")

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

            if want_netns:
                cmd = [_unshare_bin(), "--net", sys.executable, str(entry)]
                profile = "subprocess+rlimits+netns"
                enforced = True
            else:
                cmd = [sys.executable, str(entry)]
                profile = "subprocess+rlimits"
                enforced = False

            t0 = _time.monotonic()
            try:
                proc = subprocess.run(
                    cmd,
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
            result = {"ran": True, "passed": passed, "exit_code": exit_code,
                      "stderr_tail": stderr,
                      "ms": round((_time.monotonic() - t0) * 1000, 1),
                      "no_network_requested": self.limits.no_network,
                      "no_network_enforced": enforced,
                      "isolation_profile": profile}
            self.last_sandbox = result
            return result

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
