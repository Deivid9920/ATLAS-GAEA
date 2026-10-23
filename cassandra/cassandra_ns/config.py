"""Configuration loading and validation for CASSANDRA.

load_config reads config.yaml and validates every section key-by-key.
Invalid or missing keys raise ValueError naming the offending key, so a
typo in the single source of truth fails loudly at the first call site
instead of silently changing an experiment.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def _require(d: dict, key: str, where: str) -> None:
    if key not in d:
        raise ValueError(f"config missing key: {where}.{key}")


def _validate_section(d: dict, where: str, keys: list[str]) -> None:
    for key in keys:
        _require(d, key, where)


def validate_config(cfg: dict) -> dict:
    """Validate the parsed config dict; return it unchanged when valid."""
    _validate_section(cfg, "", ["seed", "models", "data", "splits",
                                "probes", "stats", "generation",
                                "abstention", "ensemble", "colab"])
    if cfg["seed"] != 42:
        raise ValueError("config.seed must be 42: every random decision "
                         "in CASSANDRA is pinned to seed 42")

    models = cfg["models"]
    if not isinstance(models, list) or not models:
        raise ValueError("config.models must be a non-empty list")
    names = set()
    for m in models:
        _validate_section(m, "models[]", ["name", "layers"])
        names.add(m["name"])
        if not isinstance(m["layers"], list) or len(m["layers"]) < 2:
            raise ValueError("config.models[].layers must list >= 2 layers")
    if names != {"gpt2", "pythia-410m"}:
        raise ValueError(f"config.models must be gpt2 + pythia-410m, got {names}")

    data = cfg["data"]
    _validate_section(data, "data", ["tf_base_url", "tf_filename_template",
                                     "domains", "trivias_n", "cache_dir"])
    if "{domain}" not in data["tf_filename_template"]:
        raise ValueError("data.tf_filename_template must contain {domain}")
    if not isinstance(data["domains"], list) or len(data["domains"]) < 2:
        raise ValueError("data.domains must list the true/false domains")
    if int(data["trivias_n"]) <= 0:
        raise ValueError("data.trivias_n must be positive")

    splits = cfg["splits"]
    _validate_section(splits, "splits", ["n_folds", "group_by",
                                         "stratify_by"])
    if splits["group_by"] != "entity":
        raise ValueError("splits.group_by must be 'entity': row-wise "
                         "splits leak subjects across folds")
    if splits["stratify_by"] != ["domain", "label"]:
        raise ValueError("splits.stratify_by must be [domain, label]")
    if int(splits["n_folds"]) < 2:
        raise ValueError("splits.n_folds must be >= 2")

    probes = cfg["probes"]
    _validate_section(probes, "probes", ["types", "C_grid", "mlp_hidden",
                                         "feature_modes"])
    if not set(probes["types"]) <= {"logistic", "mlp"}:
        raise ValueError("probes.types must be a subset of [logistic, mlp]")
    if any(float(c) <= 0 for c in probes["C_grid"]):
        raise ValueError("probes.C_grid values must be positive")
    if int(probes["mlp_hidden"]) <= 0:
        raise ValueError("probes.mlp_hidden must be positive")
    if set(probes["feature_modes"]) != {"last_token", "mean_pool"}:
        raise ValueError("probes.feature_modes must be "
                         "[last_token, mean_pool]")

    stats = cfg["stats"]
    _validate_section(stats, "stats", ["n_bootstrap", "ci",
                                       "multiple_comparison"])
    if int(stats["n_bootstrap"]) < 100:
        raise ValueError("stats.n_bootstrap must be >= 100")
    if not 0.0 < float(stats["ci"]) < 1.0:
        raise ValueError("stats.ci must be in (0, 1)")
    if stats["multiple_comparison"] != "holm":
        raise ValueError("stats.multiple_comparison must be holm")

    generation = cfg["generation"]
    _validate_section(generation, "generation", ["max_new_tokens",
                                                 "temperature",
                                                 "n_prompts"])
    if int(generation["max_new_tokens"]) <= 0:
        raise ValueError("generation.max_new_tokens must be positive")
    if int(generation["n_prompts"]) <= 0:
        raise ValueError("generation.n_prompts must be positive")

    abstention = cfg["abstention"]
    _validate_section(abstention, "abstention", ["min_coverage"])
    if not 0.0 < float(abstention["min_coverage"]) < 1.0:
        raise ValueError("abstention.min_coverage must be in (0, 1)")

    ensemble = cfg["ensemble"]
    _validate_section(ensemble, "ensemble", ["enabled", "prometheus_graph"])

    colab = cfg["colab"]
    _validate_section(colab, "colab", ["auto_setup"])
    return cfg


def load_config(path: str | Path = "config.yaml") -> dict:
    """Read config.yaml, validate it key-by-key and return the dict."""
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"config file not found: {path}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(cfg, dict):
        raise ValueError(f"config root must be a mapping: {path}")
    return validate_config(cfg)


def model_layers(cfg: dict, name: str) -> list[int]:
    """Configured resid_post layers for a model name."""
    for m in cfg["models"]:
        if m["name"] == name:
            return [int(l) for l in m["layers"]]
    raise ValueError(f"model not in config.models: {name}")
