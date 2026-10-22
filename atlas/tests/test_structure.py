"""Structure contracts. Immutable.

Pins the repository layout, the config top-level keys, the Makefile
targets, the implemented-anchor status and the no-AI-marker hygiene of
the whole tree. The layout IS a contract: sibling projects document
themselves through it.
"""
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRS = [
    "atlas_ns/orchestrator", "atlas_ns/verify/plugins", "atlas_ns/audit",
    "atlas_ns/mcts", "atlas_ns/profiles/code_qa/data",
    "atlas_ns/profiles/finance_docs", "atlas_ns/safety", "atlas_ns/learning",
    "atlas_ns/lineage", "atlas_ns/bridge", "atlas_ns/memory", "atlas_ns/bench",
    "atlas_ns/fit", "scripts", "docs", "logs", "profiles/code_qa",
    "profiles/finance_docs",
]

REQUIRED_FILES = [
    "config.yaml", "Makefile", "requirements.txt", ".gitignore", "README.md",
    "docs/no_goals.md", "scripts/scaffold.py",
    "atlas_ns/verify/composite.py", "atlas_ns/audit/chain.py",
    "atlas_ns/orchestrator/machine.py", "atlas_ns/lineage/rules.py",
    "tests/test_verify_composite.py", "tests/test_audit_chain.py",
    "tests/test_orchestrator_machine.py", "tests/test_lineage_rules.py",
    "tests/test_structure.py",
]

CONFIG_KEYS = [
    "seed", "bridge", "verifier", "probe", "orchestrator", "memory",
    "mcts", "safety", "rft", "lineage", "profiles", "bench", "fit",
    "graph_versioning",
]

MAKEFILE_TARGETS = [
    "setup", "bridge-check", "chat", "run-task", "mcp-serve", "rft",
    "lineage", "bench", "audit-verify", "demo", "test", "lint", "clean",
]

FORBIDDEN_MARKERS = ["as an ai", "openai", "anthropic", "chatgpt", "glm"]

ANCHORS = ["atlas_ns/verify/composite.py", "atlas_ns/audit/chain.py",
           "atlas_ns/orchestrator/machine.py", "atlas_ns/lineage/rules.py"]


@pytest.fixture(scope="session")
def config():
    return yaml.safe_load((REPO_ROOT / "config.yaml").read_text())


@pytest.mark.parametrize("rel", REQUIRED_DIRS)
def test_dir(rel):
    assert (REPO_ROOT / rel).is_dir()


@pytest.mark.parametrize("rel", REQUIRED_FILES)
def test_file(rel):
    assert (REPO_ROOT / rel).is_file()


@pytest.mark.parametrize("key", CONFIG_KEYS)
def test_cfg(config, key):
    assert key in config


def test_verifier_taus(config):
    v = config["verifier"]
    assert 0 < v["tau_doubt"] <= v["tau_approve"] <= 1


def test_lineage_growth_keys(config):
    g = config["lineage"]["growth"]
    for k in ("min_fail_rate", "min_unrecovered_rate", "diversity_floor",
              "min_generations_between", "ceiling_params"):
        assert k in g
    assert 0 < g["min_fail_rate"] < 1 and g["ceiling_params"] > 285e6


def test_safety_contract(config):
    s = config["safety"]
    assert s["pii_scrub"] is True and s["fencing"] is True
    assert set(s["sandbox"]) >= {"timeout_s", "mem_mb", "no_network"}
    assert s["sandbox"]["no_network"] is True


def test_makefile_targets():
    text = (REPO_ROOT / "Makefile").read_text()
    declared = set(re.findall(r"^([a-zA-Z_-]+)\s*:", text, re.M))
    missing = [t for t in MAKEFILE_TARGETS if t not in declared]
    assert not missing, missing


@pytest.mark.parametrize("rel", ANCHORS)
def test_anchors_implemented(rel):
    assert "implementation pending" not in \
        (REPO_ROOT / rel).read_text(), f"{rel} is an anchor, not a stub"


def test_no_goals_document_exists():
    text = (REPO_ROOT / "docs/no_goals.md").read_text().lower()
    assert "trading" in text and "general" in text


def test_no_ai_markers():
    offenders = []
    for root in ("atlas_ns", "scripts", "docs", "profiles"):
        for p in (REPO_ROOT / root).rglob("*"):
            if p.is_file() and p.suffix in {".py", ".md", ".yaml", ".txt"}:
                low = p.read_text(errors="replace").lower()
                for m in FORBIDDEN_MARKERS:
                    if m in low:
                        offenders.append(f"{p.relative_to(REPO_ROOT)}: {m}")
    assert not offenders, offenders
