"""AtlasHook contract: identity fail-loud without touching the live
bridge (the live bridge is exercised by scripts/bridge_check.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from gv.bridge.atlas_hook import AtlasHook, BridgeError


def _config(repo):
    return {"paths": {"atlas_repo": str(repo),
                      "atlas_venv_python": str(repo / ".venv" / "bin"
                                             / "python")}}


def test_missing_atlas_repo_fails_loud(tmp_path):
    cfg = {"paths": {"atlas_repo": str(tmp_path / "nope"),
                     "atlas_venv_python": "/bin/false"}}
    with pytest.raises(BridgeError):
        AtlasHook(cfg, tmp_path)


def test_missing_venv_python_fails_loud(tmp_path):
    (tmp_path / "atlas_repo").mkdir()
    cfg = _config(tmp_path / "atlas_repo")
    with pytest.raises(BridgeError):
        AtlasHook(cfg, tmp_path)


def test_identity_drift_refused():
    cfg = {"identities": {"atlas_git_head": "deadbee",
                          "heph_binary_sha256": "2" * 64,
                          "weights_sha256": "4" * 64}}
    hook = AtlasHook.__new__(AtlasHook)
    hook._ident = {"git_head": "ecb494b",
                   "health": {"binary_sha256": "2" * 64,
                              "weights_sha256": "9" * 64}}
    with pytest.raises(BridgeError):
        hook.verify_identity(cfg)


def test_identity_match_accepted():
    cfg = {"identities": {"atlas_git_head": "ecb494b",
                          "heph_binary_sha256": "2" * 64,
                          "weights_sha256": "4" * 64}}
    hook = AtlasHook.__new__(AtlasHook)
    hook._ident = {"git_head": "ecb494b",
                   "health": {"binary_sha256": "2" * 64,
                              "weights_sha256": "4" * 64}}
    out = hook.verify_identity(cfg)
    assert out["git_head"] == "ecb494b"
