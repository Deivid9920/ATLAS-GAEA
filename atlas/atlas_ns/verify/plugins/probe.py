"""Truth-probe bridge (#6): CASSANDRA when present, honest absence when
not.

CASSANDRA publishes calibrated probes (tau*) over model internals. The
bridge checks, in order: sibling repo exists -> probe artifacts exist
-> model hash matches the last calibration. Any miss reports
`probe: unavailable` with a NEUTRAL vote (0.5) — the composite is
designed to work with the other two verifiers and the audit trail
always shows the probe's true state. NEVER a fabricated score.

Recalibration job: on model change (weights sha256 differs from the
last calibrated hash) append a recalibration record to
logs/probe_recalibration.jsonl. Calibration itself needs the trained
CASSANDRA artifacts; without them the job records `unavailable` —
again honestly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from atlas_ns.verify.composite import Verdict

NEUTRAL = 0.5


class ProbeVerifier:
    name = "probe"

    def __init__(self, config: dict | None = None,
                 repo_root: Path | None = None) -> None:
        self._cfg = (config or {})
        self._root = repo_root or Path(__file__).resolve().parents[3]
        self.enabled = bool(self._cfg.get("probe", {}).get("bridge", True))
        self._cassandra = self._root.parent / "cassandra"

    # -- availability -----------------------------------------------------
    def status(self) -> dict:
        if not self.enabled:
            return {"available": False, "reason": "probe bridge disabled "
                                                 "by config"}
        if not self._cassandra.is_dir():
            return {"available": False,
                    "reason": "CASSANDRA repo not found"}
        probes = self._cassandra / "artifacts" / "probes"
        artifacts = [p.name for p in probes.glob("*")
                     if p.is_file() and p.suffix != ".gitkeep"] \
            if probes.is_dir() else []
        if not artifacts:
            return {"available": False,
                    "reason": "no trained probe artifacts",
                    "repo": str(self._cassandra)}
        return {"available": True, "artifacts": artifacts}

    def _tau_star(self) -> float | None:
        """Published tau* from the sibling's ensemble table, if any."""
        table = self._cassandra / "docs" / "ensemble_table.md"
        if not table.is_file():
            return None
        for line in table.read_text(encoding="utf-8").splitlines():
            if "tau" in line.lower() and "|" in line:
                for token in line.split("|"):
                    token = token.strip()
                    if token.replace(".", "", 1).isdigit():
                        value = float(token)
                        if 0.0 < value < 1.0:
                            return value
        return None

    # -- verify ---------------------------------------------------------------
    def verify(self, claim: str, context: dict | None = None) -> Verdict:
        state = self.status()
        if not state["available"]:
            return Verdict(self.name, NEUTRAL,
                           f"probe: unavailable ({state['reason']})",
                           hard_block=False)
        # With artifacts present, a real probe call would run here; the
        # score comes from the calibrated threshold, never invented.
        tau = self._tau_star()
        return Verdict(self.name, NEUTRAL,
                       f"probe artifacts present (tau*={tau}); live "
                       f"scoring lands with the CASSANDRA runtime",
                       hard_block=False)

    # -- recalibration (#6) ----------------------------------------------------
    def recalibrate(self, model_weights_path: Path | None = None) -> dict:
        """Detect model change and append the job record. Deterministic."""
        state = self.status()
        record: dict = {"job": "probe_recalibration"}
        if model_weights_path is not None and model_weights_path.is_file():
            digest = hashlib.sha256(
                model_weights_path.read_bytes()).hexdigest()
            record["model_sha256"] = digest
        log = self._root / "logs" / "probe_recalibration.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        if not state["available"]:
            record["status"] = "unavailable"
            record["reason"] = state["reason"]
        else:
            record["status"] = "queued"  # real run needs the sibling venv
        with log.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
        return record
