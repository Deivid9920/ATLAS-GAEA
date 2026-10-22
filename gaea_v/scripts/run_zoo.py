"""run_zoo: FASE 3 — zoo de hackers contra el verificador compuesto
actual de ATLAS (0.45/0.35/0.20, taus 0.80/0.35).

Produces ZOO_BASELINE: global catch rate, per-category catch, FPR on
the family-paired clean set. Honest outcome rule: the baseline is
frozen and reported EVEN IF the current config fails the frozen
thresholds (S-08: the fix belongs to ATLAS's gates, never to editing
the zoo).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gv.audit.chain import AuditChain  # noqa: E402
from gv.bridge.atlas_hook import AtlasHook  # noqa: E402
from gv.canon import canonical, config_sha256  # noqa: E402
from gv.harness.task_ladder import load_ladder  # noqa: E402
from gv.zoo.registry import ATTACKS, thresholds  # noqa: E402


def main() -> int:
    rerun = "--rerun" in sys.argv  # post-fix regression re-run
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    limits = thresholds(config)
    ladder = load_ladder(ROOT / "profiles")
    by_family: dict[str, list[dict]] = {}
    for task in ladder:
        base = task["family"]
        by_family.setdefault(base, []).append(task)

    chain_path = ROOT / "logs" / "audit.jsonl"
    chain = AuditChain.load(chain_path) if chain_path.exists() \
        else AuditChain()
    hook = AtlasHook(config, ROOT)
    try:
        hook.verify_identity(config)
        rows = []
        cache_results = None

        for attack in ATTACKS:
            payload = attack["generate"](attack["seed"])
            rule = attack["capture_rule"]
            expected = attack["expected_verdict"]
            if rule == "property_holds":
                if cache_results is None:
                    cache_results = hook.cache_probe()
                case = payload.get("case")
                result = next((r for r in cache_results
                               if r["case"] == case), None)
                if result is None:
                    raise RuntimeError(f"{attack['id']}: case {case} "
                                       f"not probed")
                captured = bool(result["holds"])
                decision = "approve" if captured else "revise"
            elif rule == "no_delta":
                pair = hook.echo_pair(payload["code"],
                                      payload["echo_code"],
                                      payload["tests"],
                                      payload["triplets"])
                captured = pair["base"]["decision"] == \
                    pair["echo"]["decision"]
                decision = pair["base"]["decision"]
            else:
                verdict = hook.evaluate(payload["code"],
                                        payload["tests"],
                                        payload["triplets"])
                decision = verdict["decision"]
                captured = decision in attack["allowed_verdicts"] \
                    if rule == "verdict_in" \
                    else decision == expected
            rows.append({"id": attack["id"],
                         "category": attack["category"],
                         "expected": expected, "decision": decision,
                         "captured": captured, "rule": rule,
                         "clean_family": attack["clean_family"]})

        clean_rows = []
        seen_pairs = set()
        for attack in ATTACKS:
            if attack["clean_family"] in seen_pairs:
                continue
            seen_pairs.add(attack["clean_family"])
            cands = by_family.get(attack["clean_family"]) or []
            task = cands[0]
            verdict = hook.evaluate(task["canonical_solution"],
                                    task["tests"], task["triplets"])
            clean_rows.append({"clean_pair_id": task["id"],
                               "family": task["family"],
                               "expected": "approve",
                               "decision": verdict["decision"],
                               "false_positive": verdict["decision"]
                               != "approve"})

        categories = sorted({r["category"] for r in rows})
        per_cat = {}
        for cat in categories:
            cat_rows = [r for r in rows if r["category"] == cat]
            per_cat[cat] = round(sum(1 for r in cat_rows if
                                     r["captured"]) / len(cat_rows),
                                 4)
        catch_global = round(sum(1 for r in rows if r["captured"])
                             / len(rows), 4)
        fpr_clean = round(sum(1 for r in clean_rows if
                              r["false_positive"]) / len(clean_rows),
                          4)
        passed = (catch_global >= limits["catch_global_min"]
                  and all(v >= limits["catch_category_min"]
                          for v in per_cat.values())
                  and fpr_clean <= limits["fpr_clean_max"])

        baseline = {
            "zoo_version": "2" if rerun else "1",
            "frozen_utc": datetime.now(
                timezone.utc).isoformat(timespec="seconds"),
            "config_sha256": config_sha256(ROOT / "config.yaml"),
            "verifier": {"weights": {"programmatic": 0.45,
                                     "symbolic": 0.35, "probe": 0.20},
                         "tau_approve": 0.80, "tau_doubt": 0.35,
                         "source_head": config["identities"][
                             "atlas_git_head"]},
            "thresholds": limits, "catch_global": catch_global,
            "catch_by_category": per_cat, "fpr_clean": fpr_clean,
            "pass": passed, "rows": rows, "clean_rows": clean_rows,
        }
        out = ROOT / "artifacts" / "zoo_baseline.json"
        out.write_text(json.dumps(baseline, ensure_ascii=False,
                                  indent=1) + "\n", encoding="utf-8")

        chain.append({"action": "zoo_baseline_frozen",
                      "zoo_version": "2" if rerun else "1",
                      "catch_global": catch_global,
                      "catch_by_category": per_cat,
                      "fpr_clean": fpr_clean,
                      "pass": passed,
                      "n_attacks": len(rows),
                      "n_clean": len(clean_rows)})
        if not rerun:
            chain.append({"action": "zoo_regression_rule_frozen",
                          "rule": "every future verifier config re-runs "
                                  "the zoo; promotion is refused if catch "
                                  "falls below the frozen thresholds or "
                                  "FPR rises above fpr_clean_max"})
        chain.save(chain_path)
        print(json.dumps({"step": "zoo_baseline",
                          "catch_global": catch_global,
                          "by_category": per_cat,
                          "fpr_clean": fpr_clean,
                          "pass": passed,
                          "failed_categories":
                          [k for k, v in per_cat.items()
                           if v < limits["catch_category_min"]]}))
        return 0
    finally:
        hook.close()


if __name__ == "__main__":
    raise SystemExit(main())
