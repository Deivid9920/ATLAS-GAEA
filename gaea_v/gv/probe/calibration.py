"""calibration: decision de activación del probe (contrato congelado).

Frozen decision (anchor 12): AUC IC95% excluding 0.5 activates the
probe with weight 0.20 and reports ECE; if ECE > ece_max the tau must
be recalibrated BEFORE activation; without signal the probe is
DEACTIVATED with weight 0 and cause "probe_desactivado", and the
remaining verifier weights are renormalized. The neutral 0.5 vote is
FORBIDDEN in this repo: a missing or uncalibrated probe is a state
with a cause, never a fabricated score.
"""

from __future__ import annotations

from gv.stats.stats_core import auc_ci, ece as ece_fn

WEIGHT_ON_ACTIVE = 0.20


class ProbeContractError(ValueError):
    pass


def probe_decision(scores, labels, confidences, correctness, *,
                   weight_on_active: float = WEIGHT_ON_ACTIVE,
                   ece_max: float = 0.15, resamples: int = 2000,
                   seed: int = 42) -> dict:
    """Frozen activation rule over calibration data (n=200 target).

    Returns the decision record appended to logs/probe_calibration
    .jsonl. status is 'active' or 'desactivado'; 'neutral' is not a
    representable outcome.
    """
    labels = list(labels)
    if set(labels) - {0, 1} or len(set(labels)) < 2:
        raise ProbeContractError("calibration labels need both classes")
    res = auc_ci(list(scores), labels, resamples, seed)
    cal = ece_fn(list(confidences), list(correctness))
    excludes = res["ci_lo"] > 0.5 or res["ci_hi"] < 0.5
    if excludes:
        if cal > ece_max:
            decision = {"status": "desactivado",
                        "cause": "probe_desactivado_ece_alto",
                        "recalibrate_tau": True,
                        "weight": 0.0,
                        "renormalized_weights": None}
        else:
            decision = {"status": "active", "cause": "auc_ci_excludes_050",
                        "recalibrate_tau": False,
                        "weight": weight_on_active,
                        "renormalized_weights": None}
    else:
        decision = {"status": "desactivado",
                    "cause": "probe_desactivado",
                    "recalibrate_tau": False, "weight": 0.0,
                    "renormalized_weights": None}
    decision.update({"auc": res["auc"], "ci_lo": res["ci_lo"],
                     "ci_hi": res["ci_hi"], "ece": cal,
                     "ece_max": ece_max, "seed": seed})
    return decision


def renormalize(weights: dict, disabled_name: str) -> dict:
    """Renormalize plugin weights after a deactivation (S-06 math).

    0.45/0.35/0.20 with the probe at 0 becomes 0.5625/0.4375.
    """
    if disabled_name not in weights:
        raise ProbeContractError(f"unknown plugin {disabled_name}")
    rest = {k: v for k, v in weights.items() if k != disabled_name}
    total = sum(rest.values())
    if total <= 0:
        raise ProbeContractError("no active weight left to renormalize")
    return {k: v / total for k, v in rest.items()}
