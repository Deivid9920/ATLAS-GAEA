"""Anchor 1: structure, config keys, Makefile targets, FORBIDDEN
markers. The FORBIDDEN_MARKERS list is inherited verbatim from ATLAS
tests/test_structure.py."""
from __future__ import annotations

import yaml

REPO_ROOT = __file__.rsplit("/tests/", 1)[0]
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

FORBIDDEN_MARKERS = ["as an ai", "openai", "anthropic", "chatgpt",
                     "glm"]

REQUIRED_DIRS = [
    "docs", "gv", "gv/audit", "gv/stats", "gv/harness",
    "gv/contamination", "gv/zoo", "gv/zoo/attacks", "gv/probe",
    "gv/bridge", "gv/lin", "profiles/code_qa", "profiles/finance_docs",
    "artifacts/prereg", "artifacts/runs", "logs", "scripts", "tests",
]

REQUIRED_FILES = [
    "Makefile", "README.md", "config.yaml", "requirements.txt",
    "no_goals.md", "gv/canon.py", "gv/audit/chain.py",
    "gv/stats/stats_core.py", "gv/stats/prereg.py",
    "gv/harness/runner.py", "gv/harness/task_ladder.py",
    "gv/harness/efficiency_manifest.py",
    "gv/contamination/fingerprints.py", "gv/contamination/gates.py",
    "gv/zoo/registry.py", "gv/probe/calibration.py",
    "gv/probe/cassandra_bridge.py", "gv/bridge/atlas_hook.py",
    "gv/bridge/policy_contract.py", "gv/lin/matching.py",
    "scripts/audit_verify.py", "scripts/run_pilot_power.py",
    "scripts/run_zoo.py", "scripts/run_eval.py",
    "scripts/package_release.py",
]

TEST_FILES = [
    "tests/test_structure.py", "tests/test_audit_chain.py",
    "tests/test_stats_core.py", "tests/test_holm.py",
    "tests/test_tost.py", "tests/test_paired_bootstrap.py",
    "tests/test_power.py", "tests/test_task_ladder.py",
    "tests/test_contamination.py", "tests/test_zoo_registry.py",
    "tests/test_efficiency_manifest.py", "tests/test_probe_contract.py",
    "tests/test_policy_contract.py", "tests/test_prereg.py",
    "tests/test_runner.py", "tests/test_matching.py",
    "tests/test_atlas_hook.py",
]

CONFIG_KEYS = ["seed", "identities", "suite", "stats", "probe", "zoo",
               "contamination", "rft", "manifest_schema_version",
               "flops_formula", "paths", "pilot"]

MAKE_TARGETS = ["test", "audit-verify", "bridge-check", "pilot",
                "eval", "zoo", "rft", "bench", "package"]


def test_forbidden_markers():
    offenders = []
    # same scan policy as the ATLAS anchor: code and docs trees, plus
    # the root contract files; the marker list itself lives in tests/
    roots = ["gv", "scripts", "docs", "profiles"]
    files = ["README.md", "no_goals.md", "config.yaml",
             "requirements.txt", "Makefile"]
    targets = [p for root in roots
               for p in (REPO_ROOT / root).rglob("*") if p.is_file()]
    targets += [REPO_ROOT / f for f in files]
    skip_parts = {".venv", "__pycache__", ".pytest_cache"}
    for p in targets:
        if not p.is_file() or skip_parts & set(p.parts):
            continue
        if p.suffix not in (".py", ".md", ".yaml", ".txt", ".jsonl",
                            ".json", ""):
            continue
        try:
            low = p.read_text(encoding="utf-8", errors="ignore").lower()
        except OSError:
            continue
        for m in FORBIDDEN_MARKERS:
            if m in low:
                offenders.append(f"{p.relative_to(REPO_ROOT)}: {m}")
    assert not offenders, offenders


def test_makefile_tabs_real():
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    recipes = [line for line in text.splitlines()
               if line.startswith("\t")]
    assert recipes, "Makefile recipes lost their tabs (M-03)"
    targets = {line.split(":")[0].strip() for line in
               text.splitlines()
               if line and not line.startswith((" ", "\t", "#", "."))}
    for target in MAKE_TARGETS:
        assert target in targets, f"missing make target {target}"


def test_yaml_floats_are_numeric():
    cfg = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    assert isinstance(cfg["seed"], int)
    assert isinstance(cfg["suite"]["n_total"], int)
    assert cfg["suite"]["tiers"]["t1"] == 50
    assert isinstance(cfg["stats"]["bootstrap_resamples"], int)
    assert isinstance(cfg["zoo"]["catch_global_min"], float)
    assert isinstance(cfg["probe"]["weight_on_active"], float)


def test_identity_anchors_frozen():
    cfg = yaml.safe_load((REPO_ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    ids = cfg["identities"]
    assert ids["heph_binary_sha256"].startswith("23981267")
    assert ids["weights_sha256"].startswith("499e8c53")
    assert ids["holdout_digest"].startswith("62d8992a3add")
    # Puntero de head actualizado por enmienda encadenada (ronda 2 de
    # protocolo, v1.2.0): 4427672 (línea histórica muerta) -> 4582400.
    # Las identidades S-01 (heph/pesos/holdout) permanecen intactas.
    assert ids["atlas_git_head"] == "4582400"
    assert ids["prompt_maestro_sha256"].startswith("ae409daf")
    assert cfg["flops_formula"] == "flops_v1"
    assert cfg["manifest_schema_version"] == 1


def test_no_goals_declared():
    text = (REPO_ROOT / "no_goals.md").read_text(encoding="utf-8")
    assert "mide; no mejora" in text or "measure" in text
