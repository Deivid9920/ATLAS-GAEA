"""FASE 1: HEPHAESTUS bridge contract against the REAL sibling binary.

These tests exercise ../hephaestus/build/heph end to end. If the
sibling is not built they fail-loud on purpose: bridge-check is a hard
gate and so is this suite.
"""
import pytest
import yaml

from atlas_ns.bridge.hephaestus import BridgeError, HephaestusBridge

ROOT = pytest.importorskip("pathlib").Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def config():
    return yaml.safe_load((ROOT / "config.yaml").read_text())


@pytest.fixture(scope="module")
def bridge(config):
    return HephaestusBridge(config, repo_root=ROOT)


def test_resolve_bin_fail_loud(config, tmp_path):
    broken = dict(config)
    broken["bridge"] = dict(config["bridge"],
                            hephaestus_bin="nowhere/heph")
    b = HephaestusBridge(broken, repo_root=ROOT)
    with pytest.raises(BridgeError, match="fail-loud"):
        b.resolve_bin()


def test_tokenize_real_binary(bridge):
    tokens = bridge.tokenize("hello bridge")
    assert isinstance(tokens, list) and len(tokens) >= 2
    assert all(isinstance(t, int) for t in tokens)


def test_tokenize_deterministic(bridge):
    assert bridge.tokenize("seed 42") == bridge.tokenize("seed 42")


def test_generate_real_nano(bridge):
    res = bridge.generate("The meaning of", max_new_tokens=8)
    assert isinstance(res["text"], str)
    assert len(res["text"]) > 0


def test_call_json_lines_contract(bridge):
    for op, args in [("tokenize", {"text": "json lines"}),
                     ("generate", {"prompt": "Hi",
                                   "max_new_tokens": 4}),
                     ("health", {})]:
        res = bridge.call(op, args)
        assert res["ok"] is True and res["op"] == op


def test_call_unknown_op_fails_loud(bridge):
    with pytest.raises(BridgeError, match="unknown op"):
        bridge.call("rm_rf", {})


def test_health_reports_hashes(bridge):
    h = bridge.health()
    assert h["ok"] is True
    assert len(h["binary_sha256"]) == 64
    assert len(h["weights_sha256"]) == 64
