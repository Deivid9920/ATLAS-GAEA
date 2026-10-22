"""atlas_hook: puente de SOLO LECTURA hacia el repo hermano atlas/.

It never imports ATLAS to modify it; it drives it as a subprocess
(same pattern as the heph bridge) and reads its artifacts. Identity
is fail-loud: a git head or binary/weights hash that differs from the
frozen anchors in config.yaml refuses the whole run — never tolerated
in silence.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


class BridgeError(RuntimeError):
    pass


class AtlasHook:
    def __init__(self, config: dict, repo_root: Path) -> None:
        self.root = Path(repo_root).resolve()
        paths = config["paths"]
        self.atlas_dir = (self.root / paths["atlas_repo"]).resolve()
        # normpath, NOT resolve(): the venv python is a symlink and
        # resolving it launches the base interpreter without the venv
        # site-packages (the exact S-05 failure mode).
        python = os.path.normpath(self.root / paths["atlas_venv_python"])
        if not os.path.exists(python):
            raise BridgeError(f"atlas venv python missing: {python}")
        if not self.atlas_dir.is_dir():
            raise BridgeError(f"atlas repo missing: {self.atlas_dir}")
        self._python = str(python)
        worker = self.root / "gv" / "bridge" / "worker_atlas.py"
        self._proc = subprocess.Popen(
            [self._python, str(worker)], cwd=str(self.atlas_dir),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self._ident: dict | None = None

    # -- protocol ---------------------------------------------------------
    def request(self, op: str, **args) -> dict:
        if self._proc.poll() is not None:
            raise BridgeError("atlas worker died before request")
        assert self._proc.stdin is not None
        assert self._proc.stdout is not None
        self._proc.stdin.write(json.dumps({"op": op, "args": args})
                               + "\n")
        self._proc.stdin.flush()
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise BridgeError(f"atlas worker closed on op {op}")
            line = line.strip()
            if not line.startswith("{"):
                continue  # stray import noise never enters the protocol
            resp = json.loads(line)
            if not resp.get("ok"):
                raise BridgeError(f"atlas op {op} failed: "
                                  f"{resp.get('error')}")
            return resp

    # -- identity ---------------------------------------------------------
    def identity(self) -> dict:
        if self._ident is None:
            resp = self.request("identity")
            self._ident = {"git_head": resp["git_head"],
                           "health": resp["health"]}
        return self._ident

    def verify_identity(self, config: dict) -> dict:
        ident = self.identity()
        anchors = config["identities"]
        if ident["git_head"] != anchors["atlas_git_head"]:
            raise BridgeError(
                f"ATLAS git head drifted: {ident['git_head']} != "
                f"{anchors['atlas_git_head']}")
        health = ident["health"]
        if health["binary_sha256"] != anchors["heph_binary_sha256"]:
            raise BridgeError("heph binary hash drifted from anchor")
        if health["weights_sha256"] != anchors["weights_sha256"]:
            raise BridgeError("weights hash drifted from frozen "
                              "champion tag")
        return {"git_head": ident["git_head"],
                "binary_sha256": health["binary_sha256"],
                "weights_sha256": health["weights_sha256"]}

    # -- operations --------------------------------------------------------
    def build_t1(self, n: int = 50, seed: int = 42) -> list[dict]:
        return self.request("build_t1", n=n, seed=seed)["tasks"]

    def solve(self, task: dict, mode: str = "atlas",
              budget: str = "fast", max_iters: int = 3,
              prune_mode: str = "verifier",
              answer_cap: int = 0) -> dict:
        return self.request("solve", task=task, mode=mode,
                            budget=budget, max_iters=max_iters,
                            prune_mode=prune_mode,
                            answer_cap=answer_cap)

    def lineage_decide(self, metrics: dict) -> dict:
        """G1-G4 decision produced by ATLAS's own frozen rules code.

        gv supplies measured metrics only; thresholds and the decision
        function come from ATLAS (read-only), never re-implemented here.
        """
        return self.request("lineage_decide", metrics=metrics)

    def cpu_seconds(self) -> float:
        """CPU seconds (user+sys, self+reaped children) of the worker.

        getrusage(RUSAGE_CHILDREN) only counts REAPED children; the
        worker stays alive for the whole run, so its CPU would vanish
        from the harness frontier. This reads /proc/<pid>/stat
        (utime+stime+cutime+cstime) — a measured number, not a model.
        Returns 0.0 if the proc entry is gone (already reaped).
        """
        try:
            with open(f"/proc/{self._proc.pid}/stat", "rb") as fh:
                raw = fh.read()
        except OSError:
            return 0.0
        try:
            after = raw[raw.rindex(b")") + 1:].split()
            utime, stime, cutime, cstime = (int(after[i])
                                            for i in (11, 12, 13, 14))
            ticks = os.sysconf("SC_CLK_TCK")
            return (utime + stime + cutime + cstime) / ticks
        except (ValueError, IndexError):
            return 0.0

    def generate(self, prompt: str, max_new_tokens: int = 48,
                 temperature: float = 0.8,
                 weights_variant: str = "fp32") -> dict:
        return self.request("generate", prompt=prompt,
                            max_new_tokens=max_new_tokens,
                            temperature=temperature,
                            weights_variant=weights_variant)

    def evaluate(self, code: str, tests: str,
                 triplets: list | None = None) -> dict:
        return self.request("evaluate", code=code, tests=tests,
                            triplets=triplets or [])["verdict"]

    def echo_pair(self, base_code: str, echo_code: str, tests: str,
                  triplets: list | None = None) -> dict:
        return self.request("echo_pair", base_code=base_code,
                            echo_code=echo_code, tests=tests,
                            triplets=triplets or [])

    def cache_probe(self) -> list[dict]:
        return self.request("cache_probe")["results"]

    def run_tests(self, code: str, tests: str) -> dict:
        return self.request("run_tests", code=code, tests=tests)

    def close(self) -> None:
        if self._proc.poll() is None:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
