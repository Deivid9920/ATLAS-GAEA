"""Harness runner tests: self+children CPU measured at one frontier
(M-04), per_task rows, manifest emission, suite mismatch refusal."""
import json

import subprocess
import sys
import time

import pytest

from gv.harness.runner import (run_condition, assert_same_suite,
                               SuiteMismatchError)


def _tasks(n: int = 3):
    return [{"id": f"T1-{i:04d}", "tier": "t1", "family": "f",
             "prompt": "p", "tests": "t", "canonical_solution": "s",
             "triplets": [], "seed": 42} for i in range(n)]


def _solver_factory(burn_children: bool):
    def solver(task):
        if burn_children:
            subprocess.run([sys.executable, "-c",
                            "x = sum(i*i for i in range(2_000_000))"],
                           check=True)
        return {"tests_passed": True, "decision": "approve"}
    return solver


def _run(tmp_path, burn_children=False):
    return run_condition(
        "pilot_test", _tasks(3), _solver_factory(burn_children),
        tmp_path, config_sha256="c" * 64, git_head="g" * 7,
        atlas_git_head="ecb494b", heph_binary_sha256="2" * 64,
        weights_sha256="4" * 64, seed=42)


def test_children_cpu_is_measured(tmp_path):
    with_child = _run(tmp_path, burn_children=True)
    assert with_child["cpu_s_children"] > 0.0, \
        "subprocess work must appear in the measurement (M-04)"
    assert with_child["cpu_s_total"] == pytest.approx(
        with_child["cpu_s_self"] + with_child["cpu_s_children"],
        abs=1e-3)


def test_per_task_and_manifest_emitted(tmp_path):
    manifest = _run(tmp_path)
    run_dir = tmp_path / manifest["run_id"]
    rows = [json.loads(line) for line in
            (run_dir / "per_task.jsonl").read_text().splitlines()]
    assert len(rows) == 3
    assert all(r["tests_passed"] for r in rows)
    assert manifest["n_tasks"] == 3
    assert manifest["accuracy_overall"] == 1.0
    assert manifest["verdict_histogram"]["approve"] == 3
    assert (run_dir / "manifest.json").exists()


def test_suite_digest_recorded(tmp_path):
    m1 = _run(tmp_path / "a")
    m2 = _run(tmp_path / "b")
    assert m1["suite_digest"] == m2["suite_digest"]
    assert_same_suite(m1["suite_digest"], m2["suite_digest"])
    with pytest.raises(SuiteMismatchError):
        assert_same_suite(m1["suite_digest"], "f" * 64)


def test_unknown_decision_fails_loud(tmp_path):
    def bad_solver(task):
        return {"tests_passed": True, "decision": "maybe"}
    with pytest.raises(ValueError):
        run_condition("pilot_test", _tasks(1), bad_solver, tmp_path,
                      config_sha256="c" * 64, git_head="g" * 7,
                      atlas_git_head="ecb494b",
                      heph_binary_sha256="2" * 64,
                      weights_sha256="4" * 64)


def test_child_cpu_probe_delta_is_added(tmp_path):
    """A LIVE child's CPU (worker alive the whole run) must enter the
    frontier: the probe delta is added to cpu_s_children (M-04 fix)."""
    counter = {"calls": 0}

    def probe():
        counter["calls"] += 1
        return 0.0 if counter["calls"] == 1 else 2.5

    m = run_condition(
        "pilot_test", _tasks(2), _solver_factory(False), tmp_path,
        config_sha256="c" * 64, git_head="g" * 7,
        atlas_git_head="ecb494b", heph_binary_sha256="2" * 64,
        weights_sha256="4" * 64, seed=42, child_cpu_probe=probe)
    assert m["cpu_s_children"] >= 2.5
    assert m["cpu_s_total"] == pytest.approx(
        m["cpu_s_self"] + m["cpu_s_children"], abs=1e-3)


def test_child_cpu_probe_negative_delta_ignored(tmp_path):
    flaky = {"v": 1.0}

    def probe():
        flaky["v"] -= 5.0
        return flaky["v"]

    m = run_condition(
        "pilot_test", _tasks(2), _solver_factory(False), tmp_path,
        config_sha256="c" * 64, git_head="g" * 7,
        atlas_git_head="ecb494b", heph_binary_sha256="2" * 64,
        weights_sha256="4" * 64, seed=42, child_cpu_probe=probe)
    assert m["cpu_s_children"] >= 0.0


def test_manifest_carries_gaea_l_nulls(tmp_path):
    m = _run(tmp_path)
    assert m["substrate_id"] is None
    assert m["matching_params"] is None
    assert m["matching_training_flops"] is None


def test_manifest_gaea_l_fields_populated(tmp_path):
    gaea_l = {"substrate_id": "stub_substrate",
              "matching_params": 1000,
              "matching_training_flops": 2000}
    m = run_condition(
        "stub_substrate", _tasks(2), _solver_factory(False), tmp_path,
        config_sha256="c" * 64, git_head="g" * 7,
        atlas_git_head="ecb494b", heph_binary_sha256="2" * 64,
        weights_sha256="4" * 64, seed=42, gaea_l=gaea_l)
    assert m["substrate_id"] == "stub_substrate"
    assert m["matching_params"] == 1000
    assert m["matching_training_flops"] == 2000
