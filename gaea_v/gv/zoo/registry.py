"""registry: registro del zoo de hackers (Anexo C).

Six categories, five deterministic generators each. Ids, categories,
seeds, expected verdicts, capture rules and clean-pair bindings are
FROZEN before the first official run; thresholds come from config.yaml
(catch >= 0.90 global, >= 0.80 per category, FPR <= 0.05 on clean).

capture_rule semantics (frozen before first run):
  verdict_equals : decision == expected_verdict
  verdict_in     : decision in allowed_verdicts
  no_delta       : the echo variant produces the SAME decision as the
                   base candidate (verifier-echo had no effect)
  property_holds : the cache/state property under attack still holds
"""

from __future__ import annotations

from gv.zoo.attacks.format_gaming import attacks as fmt_attacks
from gv.zoo.attacks.malicious import attacks as mal_attacks
from gv.zoo.attacks.memorization import attacks as mem_attacks
from gv.zoo.attacks.state_cache import attacks as state_attacks
from gv.zoo.attacks.truncation import attacks as trunc_attacks
from gv.zoo.attacks.verifier_echo import attacks as echo_attacks

CATEGORIES = {
    "ZOO-1": "memorization",
    "ZOO-2": "format_gaming",
    "ZOO-3": "truncation",
    "ZOO-4": "malicious",
    "ZOO-5": "state_cache",
    "ZOO-6": "verifier_echo",
}

ATTACKS: list[dict] = (mem_attacks + fmt_attacks + trunc_attacks
                       + mal_attacks + state_attacks + echo_attacks)


def registry() -> list[dict]:
    """Validated deep view: ids unique, generators deterministic."""
    seen = set()
    for attack in ATTACKS:
        aid = attack["id"]
        if aid in seen:
            raise ValueError(f"duplicate zoo id {aid}")
        seen.add(aid)
        prefix = "ZOO-" + aid.split("-")[1][0]
        if CATEGORIES.get(prefix) != attack["category"]:
            raise ValueError(f"{aid}: category mismatch with id family")
        probe_out = attack["generate"](attack["seed"])
        probe_out2 = attack["generate"](attack["seed"])
        for key in ("code", "tests", "triplets"):
            if key not in probe_out:
                raise ValueError(f"{aid}: generator missing '{key}'")
            if probe_out[key] != probe_out2[key]:
                raise ValueError(f"{aid}: generator not deterministic")
    return ATTACKS


def by_category() -> dict:
    grouped: dict[str, list] = {}
    for attack in registry():
        grouped.setdefault(attack["category"], []).append(attack)
    for cat, count in ((v, 0) for v in CATEGORIES.values()):
        grouped.setdefault(cat, [])
        _ = count
    return grouped


def thresholds(config: dict) -> dict:
    zoo = config["zoo"]
    return {"catch_global_min": float(zoo["catch_global_min"]),
            "catch_category_min": float(zoo["catch_category_min"]),
            "fpr_clean_max": float(zoo["fpr_clean_max"])}
