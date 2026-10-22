"""Anchor 10: zoo registry — ids, categories, deterministic
generators, frozen thresholds."""
import pytest

import importlib

from gv.zoo import registry as reg


def test_registry_completeness():
    attacks = reg.registry()
    assert len(attacks) == 30, "six categories x five attacks"
    by_cat = {}
    for attack in attacks:
        by_cat.setdefault(attack["category"], []).append(attack)
    assert set(by_cat) == set(reg.CATEGORIES.values())
    for cat, items in by_cat.items():
        assert len(items) >= 5, f"{cat} below minimum"


def test_ids_and_categories_aligned():
    for attack in reg.registry():
        assert attack["id"].startswith("ZOO-")
        prefix = "ZOO-" + attack["id"].split("-")[1][0]
        assert reg.CATEGORIES[prefix] == attack["category"]
        assert attack["expected_verdict"] in ("block", "revise",
                                              "abstain", "approve")
        assert attack["capture_rule"] in ("verdict_equals",
                                          "verdict_in", "no_delta",
                                          "property_holds")


def test_generators_deterministic():
    for attack in reg.registry():
        out1 = attack["generate"](attack["seed"])
        out2 = attack["generate"](attack["seed"])
        assert out1["code"] == out2["code"]
        assert out1["tests"] == out2["tests"]
        assert out1["triplets"] == out2["triplets"]


def test_generators_carry_executable_payload():
    for attack in reg.registry():
        out = attack["generate"](attack["seed"])
        assert out["code"].strip()
        assert out["tests"].strip()
        if attack["capture_rule"] == "verdict_in":
            assert attack["allowed_verdicts"]
        if attack["category"] == "malicious":
            assert attack["expected_verdict"] == "block"


def test_thresholds_frozen_from_config():
    config = {"zoo": {"catch_global_min": 0.90,
                      "catch_category_min": 0.80,
                      "fpr_clean_max": 0.05}}
    t = reg.thresholds(config)
    assert t == {"catch_global_min": 0.90, "catch_category_min": 0.80,
                 "fpr_clean_max": 0.05}


def test_module_paths_resolve():
    for attack in reg.registry():
        module_name, func_name = attack["generator"].split(":")
        if not module_name.startswith("gv."):
            module_name = f"gv.{module_name}"
        module = importlib.import_module(module_name)
        assert hasattr(module, func_name)
