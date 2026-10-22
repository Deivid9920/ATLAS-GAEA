"""Anchor 11: efficiency manifest schema v1 — closed schema, unknown
fields rejected, cpu identity, probe status never neutral."""
import pytest

from gv.harness.efficiency_manifest import (validate_manifest,
                                            ManifestError,
                                            accuracy_per_cpu_s,
                                            SCHEMA_VERSION)


def _manifest(**over):
    base = {
        "run_id": "run1234abcd", "schema_version": SCHEMA_VERSION,
        "created_utc": "2026-10-20T00:00:00+00:00",
        "config_sha256": "c" * 64, "git_head": "a" * 7,
        "atlas_git_head": "ecb494b",
        "heph_binary_sha256": "2" * 64, "weights_sha256": "4" * 64,
        "profile": "code_qa", "suite_digest": "d" * 64, "n_tasks": 100,
        "seed": 42, "condition": "pilot_atlas", "prereg_sha256": None,
        "accuracy_overall": 0.5,
        "accuracy_by_tier": {"t1": 1.0, "t2": 0.3, "t3": 0.2},
        "verdict_histogram": {"approve": 30, "revise": 20, "block": 0,
                              "abstain": 0},
        "cpu_s_self": 10.0, "cpu_s_children": 5.0, "cpu_s_total": 15.0,
        "wall_s": 20.0, "rss_peak_mb": 120.5, "mcts_nodes_total": 400,
        "mcts_nodes_per_s": 26.67, "tokens_generated": 4800,
        "flops_analytic_total": 4800 * 10616832,
        "accuracy_per_cpu_s": 0.5 / 15.0, "bridge_mode": "fp32",
        "probe_status": "desactivado", "probe_auc": None,
        "probe_ece": None, "zoo": None,
        "contamination": {"ngram_hits": 0, "exact_hits": 0,
                          "status": "ok"},
        "seeds_training": [], "notes": "",
        "substrate_id": None, "matching_params": None,
        "matching_training_flops": None,
    }
    base.update(over)
    return base


def test_valid_manifest_passes():
    validate_manifest(_manifest())


def test_unknown_field_rejected():
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(extra_field=1))


def test_missing_field_rejected():
    broken = _manifest()
    del broken["cpu_s_total"]
    with pytest.raises(ManifestError):
        validate_manifest(broken)


def test_cpu_identity_enforced():
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(cpu_s_total=16.0))


def test_probe_neutral_is_not_representable():
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(probe_status="neutral"))


def test_zero_cpu_forces_null_star_metric():
    m = _manifest(cpu_s_self=0.0, cpu_s_children=0.0, cpu_s_total=0.0,
                  mcts_nodes_per_s=0.0, accuracy_per_cpu_s=None)
    validate_manifest(m)


def test_inferential_condition_requires_prereg():
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(condition="atlas"))
    validate_manifest(_manifest(condition="atlas",
                                prereg_sha256="p" * 64))


def test_histogram_and_tiers_closed():
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(verdict_histogram={"approve": 1}))
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(accuracy_by_tier={"t1": 1.0}))


def test_star_metric_identity():
    assert accuracy_per_cpu_s(0.5, 0) is None
    assert accuracy_per_cpu_s(0.5, 10) == pytest.approx(0.05)


def test_gaea_l_all_null_passes():
    validate_manifest(_manifest())


def test_gaea_l_all_present_passes():
    m = _manifest(substrate_id="mamba2_s",
                  matching_params=54775296,
                  matching_training_flops=10_616_832 * 1000)
    validate_manifest(m)


def test_gaea_l_partial_is_rejected():
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(substrate_id="mamba2_s"))
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(matching_params=100))


def test_gaea_l_requires_positive_axes():
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(substrate_id="mamba2_s",
                                    matching_params=0,
                                    matching_training_flops=100))
    with pytest.raises(ManifestError):
        validate_manifest(_manifest(substrate_id="mamba2_s",
                                    matching_params=100,
                                    matching_training_flops=-1))
