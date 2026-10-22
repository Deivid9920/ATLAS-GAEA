"""FASE 1: tool permissions are fail-closed and audited."""
import pytest
import yaml

from atlas_ns.safety.permissions import (
    PermissionError, PermissionTable, from_config)

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def test_config_grants_load():
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    table = from_config(cfg)
    assert table.check("hephaestus", "execute")
    assert table.check("filesystem", "write")
    assert table.check("network_crawl", "readonly")


def test_fail_closed_unknown_tool():
    table = PermissionTable({"hephaestus": "execute"})
    assert not table.check("unknown_tool", "readonly")
    with pytest.raises(PermissionError):
        table.require("unknown_tool", "readonly")


def test_rank_ordering():
    table = PermissionTable({"t": "execute"})
    assert table.check("t", "readonly")   # execute implies readonly
    assert table.check("t", "write")
    assert table.check("t", "execute")
    low = PermissionTable({"t": "readonly"})
    assert low.check("t", "readonly")
    assert not low.check("t", "write")
    assert not low.check("t", "execute")


def test_bad_level_rejected():
    with pytest.raises(ValueError):
        PermissionTable({"t": "root"})


def test_require_returns_audit_event():
    table = PermissionTable({"hephaestus": "execute"})
    event = table.require("hephaestus", "execute")
    assert event["action"] == "permission_check"
    assert event["allowed"] is True
    assert event["tool"] == "hephaestus"
