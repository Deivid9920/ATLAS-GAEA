"""efficiency_manifest: esquema v1 del manifiesto de eficiencia.

Closed schema (Anexo A): unknown fields are rejected, every run emits
exactly one manifest, cpu_s_total == self + children, and
probe_status is never "neutral" (the neutral 0.5 is forbidden in this
repo — a missing or miscalibrated probe is declared with a cause).
"""

from __future__ import annotations

SCHEMA_VERSION = "gv.manifest/1"

FLOAT_NONNEG = ("cpu_s_self", "cpu_s_children", "wall_s", "rss_peak_mb",
                "mcts_nodes_per_s")
INT_NONNEG = ("n_tasks", "seed", "mcts_nodes_total", "tokens_generated",
              "flops_analytic_total")
CONDITIONS = ("nano_solo", "atlas", "atlas_int8", "zoo", "rft_round_k")
BRIDGE_MODES = ("fp32", "int8", "ternary")
PROBE_STATUSES = ("active", "desactivado")
VERDICT_KEYS = ("approve", "revise", "block", "abstain")
TIER_KEYS = ("t1", "t2", "t3")

REQUIRED_FIELDS = (
    "run_id", "schema_version", "created_utc", "config_sha256",
    "git_head", "atlas_git_head", "heph_binary_sha256",
    "weights_sha256", "profile", "suite_digest", "n_tasks", "seed",
    "condition", "prereg_sha256", "accuracy_overall",
    "accuracy_by_tier", "verdict_histogram", "cpu_s_self",
    "cpu_s_children", "cpu_s_total", "wall_s", "rss_peak_mb",
    "mcts_nodes_total", "mcts_nodes_per_s", "tokens_generated",
    "flops_analytic_total", "accuracy_per_cpu_s", "bridge_mode",
    "probe_status", "probe_auc", "probe_ece", "zoo", "contamination",
    "seeds_training", "notes",
    # GAEA-L reserved fields (FASE 6.d amendment, 2026-10-21): all
    # three null when the condition is not a GAEA substrate; all three
    # present together when it is. Matching on parameters alone biases
    # toward SSMs, so both axes are mandatory whenever reported.
    "substrate_id", "matching_params", "matching_training_flops",
)
GAEA_L_FIELDS = ("substrate_id", "matching_params",
                 "matching_training_flops")


class ManifestError(ValueError):
    pass


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ManifestError(msg)


def validate_manifest(m: dict) -> None:
    unknown = set(m) - set(REQUIRED_FIELDS)
    _require(not unknown, f"unknown fields rejected: {sorted(unknown)}")
    missing = set(REQUIRED_FIELDS) - set(m)
    _require(not missing, f"missing fields: {sorted(missing)}")
    _require(m["schema_version"] == SCHEMA_VERSION,
             f"schema_version must be {SCHEMA_VERSION}")
    _require(isinstance(m["run_id"], str) and m["run_id"],
             "run_id must be a non-empty string")
    _require(m["profile"] == "code_qa", "profile must be code_qa")
    _require(m["n_tasks"] == 100, "n_tasks must be 100")
    _require(isinstance(m["condition"], str) and m["condition"].strip()
             and len(m["condition"].split()) == 1,
             "condition must be a single declared identifier")
    _require(m["bridge_mode"] in BRIDGE_MODES, "bad bridge_mode")
    _require(m["probe_status"] in PROBE_STATUSES,
             "probe_status must be active or desactivado; the neutral "
             "0.5 is forbidden")
    if m["condition"] in ("atlas", "atlas_int8") or \
            m["condition"].startswith("rft_round_"):
        _require(m["prereg_sha256"] is not None,
                 "inferential condition requires prereg_sha256")
    for key in FLOAT_NONNEG:
        _require(isinstance(m[key], (int, float)) and m[key] >= 0,
                 f"{key} must be a non-negative number")
    for key in INT_NONNEG:
        _require(isinstance(m[key], int) and m[key] >= 0,
                 f"{key} must be a non-negative int")
    _require(abs(m["cpu_s_total"] - (m["cpu_s_self"]
                                     + m["cpu_s_children"])) < 1e-9,
             "cpu_s_total must equal self + children")
    _require(set(m["accuracy_by_tier"]) == set(TIER_KEYS),
             "accuracy_by_tier must have t1/t2/t3")
    for tier, acc in m["accuracy_by_tier"].items():
        _require(isinstance(acc, (int, float)) and 0.0 <= acc <= 1.0,
                 f"accuracy_by_tier[{tier}] out of [0,1]")
    _require(0.0 <= m["accuracy_overall"] <= 1.0,
             "accuracy_overall out of [0,1]")
    hist = m["verdict_histogram"]
    _require(set(hist) == set(VERDICT_KEYS) and
             all(isinstance(v, int) and v >= 0 for v in hist.values()),
             "verdict_histogram must be ints over approve/revise/block/"
             "abstain")
    if m["cpu_s_total"] == 0:
        _require(m["accuracy_per_cpu_s"] is None,
                 "accuracy_per_cpu_s must be null when cpu_s_total==0")
    else:
        expected = m["accuracy_overall"] / m["cpu_s_total"]
        _require(abs(m["accuracy_per_cpu_s"] - expected) < 1e-9,
                 "accuracy_per_cpu_s must equal accuracy/cpu_s_total")
    zoo = m["zoo"]
    _require(zoo is None or set(zoo) == {"version", "catch_rate",
                                         "fpr_clean", "pass"},
             "zoo block has a closed shape")
    cont = m["contamination"]
    _require(set(cont) == {"ngram_hits", "exact_hits", "status"},
             "contamination block has a closed shape")
    _require(cont["status"] == "ok", "contamination status must be ok")
    seeds = m["seeds_training"]
    _require(isinstance(seeds, list) and
             all(isinstance(s, int) for s in seeds),
             "seeds_training must be a list of ints")
    gaea_l = [m[f] for f in GAEA_L_FIELDS]
    present = [v is not None for v in gaea_l]
    _require(all(present) or not any(present),
             "GAEA-L fields are all-or-nothing: matching_params and "
             "matching_training_flops are always reported together")
    if all(present):
        sid, mp, mf = gaea_l
        _require(isinstance(sid, str) and sid.strip()
                 and len(sid.split()) == 1,
                 "substrate_id must be a single declared identifier")
        _require(isinstance(mp, int) and mp > 0,
                 "matching_params must be a positive int")
        _require(isinstance(mf, int) and mf > 0,
                 "matching_training_flops must be a positive int")


def accuracy_per_cpu_s(accuracy: float, cpu_s_total: float):
    if cpu_s_total == 0:
        return None
    return accuracy / cpu_s_total
