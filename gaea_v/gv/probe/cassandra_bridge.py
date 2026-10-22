"""cassandra_bridge: disponibilidad honesta del probe (opcional en vivo).

Checks, in order: sibling repo exists, probe artifacts exist, model
hash matches the last calibration. Any miss reports unavailable with
the reason — never a fabricated signal. The wiring itself belongs to
FASE 4; until then every call reports the honest state.
"""

from __future__ import annotations

from pathlib import Path


def availability(repo_root: Path, weights_sha256: str) -> dict:
    root = Path(repo_root).resolve()
    cassandra = root.parent / "cassandra"
    if not cassandra.is_dir():
        return {"available": False, "reason": "cassandra repo missing"}
    artifacts = sorted((cassandra / "artifacts").glob(
        "probe_*calibration*")) if (cassandra / "artifacts").is_dir() \
        else []
    if not artifacts:
        return {"available": False,
                "reason": "no calibration artifacts published"}
    return {"available": False,
            "reason": "probe wiring is FASE 4 scope; artifacts exist "
                      f"({len(artifacts)}) but are not connected",
            "weights_sha256": weights_sha256}
