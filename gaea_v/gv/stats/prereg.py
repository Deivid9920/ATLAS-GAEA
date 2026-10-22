"""Pre-registro estadístico: emite, hashea y encadena preregistros.

A prereg is written BEFORE any inferential run touches data (S-20):
the hash excludes created_utc, the hash is chained in the audit log,
and any later edit of the family breaks hash verification. Format:
Anexo B of the master spec.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from gv.audit.chain import AuditChain
from gv.canon import canonical, sha256_canonical

REQUIRED_FIELDS = (
    "prereg_id", "suite_digest", "config_sha256",
    "champion_tag_sha256", "pilot_usage", "epsilon_equivalence",
    "epsilon_derivation", "family_hypotheses", "claim_rule",
    "excluded_patterns_contamination", "interim_monitoring",
)

ALLOWED_PILOT_USAGE = ("variance_only", "none")


def prereg_hash(prereg: dict) -> str:
    """Hash WITHOUT created_utc (the only field allowed to vary)."""
    payload = {k: v for k, v in prereg.items() if k != "created_utc"}
    return sha256_canonical(payload)


def validate_prereg(prereg: dict) -> None:
    """Fail-loud schema check; a malformed prereg never reaches a run.

    created_utc is stamped at emission, not required from the caller.
    """
    missing = [f for f in REQUIRED_FIELDS if f not in prereg]
    if missing:
        raise ValueError(f"prereg missing fields: {missing}")
    if prereg["pilot_usage"] not in ALLOWED_PILOT_USAGE:
        raise ValueError(
            f"pilot_usage must be one of {ALLOWED_PILOT_USAGE}")
    family = prereg["family_hypotheses"]
    if not isinstance(family, list) or not family:
        raise ValueError("family_hypotheses must be a non-empty list")
    ids = [h.get("id") for h in family]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate hypothesis ids in closed family")
    for hyp in family:
        for key in ("id", "claim", "test", "direction"):
            if key not in hyp:
                raise ValueError(f"hypothesis {hyp.get('id')} "
                                 f"missing '{key}'")
        if hyp["direction"] not in ("superiority", "equivalence"):
            raise ValueError(f"hypothesis {hyp['id']}: bad direction")
    if prereg["epsilon_equivalence"] is not None \
            and prereg["epsilon_equivalence"] <= 0:
        raise ValueError("epsilon_equivalence must be positive")


def emit_prereg(prereg: dict, chain: AuditChain,
                out_dir: str | Path) -> tuple[Path, str]:
    """Validate, stamp, persist and chain a prereg. Returns path+hash."""
    validate_prereg(prereg)
    stamped = dict(prereg)
    stamped["created_utc"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds")
    digest = prereg_hash(stamped)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{stamped['prereg_id']}.json"
    if path.exists():
        raise FileExistsError(f"prereg already exists: {path}")
    path.write_text(canonical(stamped) + "\n", encoding="utf-8")
    chain.append({"action": "prereg_registered", "prereg_id":
                  stamped["prereg_id"], "prereg_sha256": digest,
                  "pilot_usage": stamped["pilot_usage"],
                  "epsilon_equivalence": stamped["epsilon_equivalence"],
                  "family_size": len(stamped["family_hypotheses"])})
    return path, digest


def verify_prereg_file(path: str | Path) -> bool:
    """Recompute the stored hash; False means the prereg was edited."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    chained = None
    log = Path(__file__).resolve().parents[2] / "logs" / "audit.jsonl"
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            event = entry.get("event") or {}
            if event.get("action") == "prereg_registered" \
                    and event.get("prereg_id") == data.get("prereg_id"):
                chained = event.get("prereg_sha256")
    return chained is not None and chained == prereg_hash(data)
