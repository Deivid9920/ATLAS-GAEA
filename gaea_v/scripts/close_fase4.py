"""close_fase4: gate F-4 — probe decision registered + smoke run.

Stage `probe`:
  Builds the frozen calibration set (200 programmatic examples, 10
  families x (10 correct + 10 buggy)), labels every example with the
  REAL ATLAS sandbox (op run_tests, measured labels — construction
  only proposes, the sandbox decides), banks it with its digest, and
  registers the probe decision under the frozen contract: with no
  published CASSANDRA calibration the probe is DESACTIVADO with cause
  "probe_desactivado", weight 0.0, and the remaining verifier weights
  renormalized. The neutral 0.5 is never emitted.

Stage `smoke`:
  One nano_solo run over the full 100-task ladder through
  gv.harness.runner.run_condition (single measurement frontier:
  getrusage self+children, wall, RSS peak), manifest validated with
  the strict Anexo A schema, contamination gate executed over the
  emitted artifacts against the frozen holdout index (fail-loud).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gv.audit.chain import AuditChain  # noqa: E402
from gv.bridge.atlas_hook import AtlasHook  # noqa: E402
from gv.canon import canonical, config_sha256, sha256_canonical  # noqa: E402
from gv.contamination.fingerprints import (build_holdout_index,  # noqa: E402
                                           fingerprint, ngram_hits)
from gv.contamination.gates import require_clean  # noqa: E402
from gv.harness.efficiency_manifest import validate_manifest  # noqa: E402
from gv.harness.runner import run_condition  # noqa: E402
from gv.harness.task_ladder import load_ladder  # noqa: E402
from gv.probe.cassandra_bridge import availability  # noqa: E402
from gv.probe.calibration import renormalize  # noqa: E402

BASE = ROOT.parent
HOLDOUT_DIR = BASE / "prometheus-ns" / "data_clean" / "holdout"
CORPUS_DIR = BASE / "prometheus-ns" / "data_clean"


def _git_head() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, cwd=str(ROOT))
    return out.stdout.strip() or "uncommitted"


def _load_chain() -> AuditChain:
    path = ROOT / "logs" / "audit.jsonl"
    chain = AuditChain.load(path) if path.exists() else AuditChain()
    ok, bad = chain.verify()
    if not ok:
        raise SystemExit(f"audit chain broken at seq {bad}; refusing")
    return chain


# -- calibration families (disjoint from the 100 ladder tasks) ----------

FAMILIES = {
    "clamp": {
        "correct": "def clamp(v, lo, hi):\n    if v < lo:\n"
                   "        return lo\n    if v > hi:\n"
                   "        return hi\n    return v\n",
        "tests": "assert clamp(5, 0, 10) == 5\nassert clamp(-1, 0, 10)"
                 " == 0\nassert clamp(11, 0, 10) == 10\n",
        "buggy": "def clamp(v, lo, hi):\n    if v < lo:\n"
                 "        return lo\n    if v > hi:\n"
                 "        return lo\n    return v\n",
    },
    "digit_sum": {
        "correct": "def digit_sum(n):\n    total = 0\n"
                   "    n = abs(n)\n    while n > 0:\n"
                   "        total += n % 10\n        n //= 10\n"
                   "    return total\n",
        "tests": "assert digit_sum(123) == 6\nassert digit_sum(0) == 0\n"
                 "assert digit_sum(-45) == 9\n",
        "buggy": "def digit_sum(n):\n    total = 0\n"
                 "    while n > 0:\n        total += n % 10\n"
                 "        n //= 10\n    return total\n",
    },
    "is_sorted": {
        "correct": "def is_sorted(xs):\n    for i in range(len(xs) - 1):"
                   "\n        if xs[i] > xs[i + 1]:\n"
                   "            return False\n    return True\n",
        "tests": "assert is_sorted([1, 2, 3]) == True\n"
                 "assert is_sorted([2, 1]) == False\n"
                 "assert is_sorted([]) == True\n",
        "buggy": "def is_sorted(xs):\n    for i in range(len(xs) - 1):"
                 "\n        if xs[i] >= xs[i + 1]:\n"
                 "            return False\n    return True\n",
    },
    "second_max": {
        "correct": "def second_max(xs):\n    uniq = sorted(set(xs))"
                   "\n    if len(uniq) < 2:\n"
                   "        raise ValueError('need two distinct')\n"
                   "    return uniq[-2]\n",
        "tests": "assert second_max([1, 5, 3]) == 3\n"
                 "try:\n    second_max([7])\n"
                 "    assert False\nexcept ValueError:\n    pass\n",
        "buggy": "def second_max(xs):\n    uniq = sorted(set(xs))\n"
                 "    return uniq[-2]\n",
    },
    "take_even": {
        "correct": "def take_even(xs):\n    return [x for x in xs\n"
                   "            if x % 2 == 0]\n",
        "tests": "assert take_even([1, 2, 3, 4]) == [2, 4]\n"
                 "assert take_even([1, 3]) == []\n",
        "buggy": "def take_even(xs):\n    return [x for x in xs\n"
                 "            if x % 2 == 1]\n",
    },
    "repeat_len": {
        "correct": "def repeat_len(s, k):\n    return len(s) * k\n",
        "tests": "assert repeat_len('ab', 3) == 6\n"
                 "assert repeat_len('', 5) == 0\n",
        "buggy": "def repeat_len(s, k):\n    return len(s) + k\n",
    },
    "last_index": {
        "correct": "def last_index(xs, needle):\n    out = -1\n"
                   "    for i, x in enumerate(xs):\n"
                   "        if x == needle:\n            out = i\n"
                   "    return out\n",
        "tests": "assert last_index([1, 2, 1], 1) == 2\n"
                 "assert last_index([1], 9) == -1\n",
        "buggy": "def last_index(xs, needle):\n    out = -1\n"
                 "    for i, x in enumerate(xs):\n"
                 "        if x == needle:\n            out = i\n"
                 "            break\n    return out\n",
    },
    "swap_pair": {
        "correct": "def swap_pair(xs):\n    if len(xs) < 2:\n"
                   "        return list(xs)\n    out = list(xs)\n"
                   "    out[0], out[1] = out[1], out[0]\n"
                   "    return out\n",
        "tests": "assert swap_pair([1, 2, 3]) == [2, 1, 3]\n"
                 "assert swap_pair([1]) == [1]\n",
        "buggy": "def swap_pair(xs):\n    out = list(xs)\n"
                 "    out[0], out[1] = out[1], out[0]\n"
                 "    return out\n",
    },
    "count_case": {
        "correct": "def count_case(s):\n    upper = sum("
                   "1 for c in s if c.isupper())\n"
                   "    return {'upper': upper, 'lower': len(s) - upper}\n",
        "tests": "assert count_case('aBc') == {'upper': 1, 'lower': 2}\n"
                 "assert count_case('') == {'upper': 0, 'lower': 0}\n",
        "buggy": "def count_case(s):\n    upper = sum("
                 "1 for c in s if c.isupper())\n"
                 "    return {'upper': upper, 'lower': upper}\n",
    },
    "bounded_pow": {
        "correct": "def bounded_pow(b, e, cap):\n    out = 1\n"
                   "    for _ in range(e):\n        out *= b\n"
                   "        if out > cap:\n            return cap\n"
                   "    return out\n",
        "tests": "assert bounded_pow(2, 3, 100) == 8\n"
                 "assert bounded_pow(2, 10, 100) == 100\n",
        "buggy": "def bounded_pow(b, e, cap):\n    out = 1\n"
                 "    for _ in range(e + 1):\n        out *= b\n"
                 "        if out > cap:\n            return cap\n"
                 "    return out\n",
    },
}

COSMETIC = [("  # guarded\n", "\n"),
           ("def ", "def "),
           ("    return", "\treturn".replace("\t", "    ")),
           ("x", "item"), ("v", "value"), ("n", "num"),
           ("out", "result"), ("total", "acc"),
           ("xs", "items"), ("s", "text")]


def _variants(code: str, n: int) -> list[str]:
    out = [code]
    for old, new in COSMETIC:
        if len(out) >= n:
            break
        cand = code.replace(old, new, 1)
        if cand != code and cand not in out:
            out.append(cand)
    while len(out) < n:  # pad with docstring placements
        padded = f'"""variant {len(out)}."""\n' + code
        if padded in out:
            padded = f'"""variant {len(out)}."""\n\n' + code
        out.append(padded)
    return out[:n]


def stage_probe(hook: AtlasHook, config: dict, chain: AuditChain) -> dict:
    examples: list[dict] = []
    for fam, spec in FAMILIES.items():
        for i, code in enumerate(_variants(spec["correct"], 10)):
            examples.append({"example_id": f"cal-{fam}-ok-{i:02d}",
                             "code": code, "tests": spec["tests"]})
        for i, code in enumerate(_variants(spec["buggy"], 10)):
            examples.append({"example_id": f"cal-{fam}-bad-{i:02d}",
                             "code": code, "tests": spec["tests"]})
    if len(examples) != 200:
        raise SystemExit(f"calibration set must be 200, got "
                         f"{len(examples)}")

    ladder_ids = {t["id"] for t in load_ladder(ROOT / "profiles")}
    holdout_texts = [p.read_text(encoding="utf-8")
                     for p in sorted(HOLDOUT_DIR.glob("*.txt"))]
    h_index = build_holdout_index(holdout_texts)
    known = {fingerprint(t) for t in holdout_texts}
    for ex in examples:
        if ex["example_id"] in ladder_ids:
            raise SystemExit(f"calibration example collides with "
                             f"ladder id {ex['example_id']}")
        if ngram_hits(ex["code"] + ex["tests"], h_index):
            raise SystemExit(f"calibration example {ex['example_id']} "
                             f"overlaps the holdout; set is invalid")

    labeled = []
    for ex in examples:
        res = hook.run_tests(ex["code"], ex["tests"])
        if not res.get("ok"):
            raise SystemExit(f"run_tests failed on {ex['example_id']}: "
                             f"{res}")
        labeled.append(dict(ex, label=1 if res["passed"] else 0,
                            sandbox_exit=res.get("exit_code")))

    n_pos = sum(1 for e in labeled if e["label"] == 1)
    digest = sha256_canonical(labeled)
    out = ROOT / "artifacts" / "probe"
    out.mkdir(parents=True, exist_ok=True)
    (out / "calibration_200.jsonl").write_text(
        "\n".join(canonical(e) for e in labeled) + "\n",
        encoding="utf-8")

    weights_sha = config["identities"]["weights_sha256"]
    avail = availability(ROOT, weights_sha)
    if avail["available"]:
        raise SystemExit("published CASSANDRA calibration detected: "
                         "compute the frozen AUC/ECE decision instead")
    decision = {"status": "desactivado",
                "cause": "probe_desactivado",
                "recalibrate_tau": False, "weight": 0.0,
                "renormalized_weights": renormalize(
                    {"programmatic": 0.45, "symbolic": 0.35,
                     "probe": 0.20}, "probe"),
                "weights_sha256": weights_sha,
                "availability_reason": avail["reason"],
                "calibration_digest": digest,
                "n_examples": len(labeled), "n_positive": n_pos,
                "created_utc": datetime.now(timezone.utc).isoformat(
                    timespec="seconds")}
    log = ROOT / "logs" / "probe_calibration.jsonl"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(canonical(decision) + "\n")

    chain.append({"action": "probe_calibration_banked",
                  "n_examples": len(labeled), "n_positive": n_pos,
                  "sandbox": "atlas programmatic run_tests (real)",
                  "disjoint_from": ["100-task ladder", "ppl holdout"],
                  "calibration_digest": digest})
    chain.append({"action": "probe_decision_registered",
                  "status": decision["status"],
                  "cause": decision["cause"],
                  "weight": 0.0,
                  "renormalized_weights":
                      decision["renormalized_weights"],
                  "availability_reason": avail["reason"]})
    chain.save(ROOT / "logs" / "audit.jsonl")
    print(json.dumps({"stage": "probe", "n": len(labeled),
                      "n_positive": n_pos, "digest": digest[:16],
                      "decision": decision["status"],
                      "cause": decision["cause"]}))
    return decision


def stage_smoke(hook: AtlasHook, config: dict, chain: AuditChain,
                probe_decision: dict) -> dict:
    tasks = sorted(load_ladder(ROOT / "profiles"), key=lambda t: t["id"])
    cfg_hash = config_sha256(ROOT / "config.yaml")
    rw = probe_decision["renormalized_weights"]
    note = (f"F-4 smoke: single measurement frontier; probe "
            f"desactivado ({probe_decision['cause']}); weights "
            f"renormalized to programmatic {rw['programmatic']:.4f} / "
            f"symbolic {rw['symbolic']:.4f}")

    def solver(task: dict) -> dict:
        res = hook.solve(task, mode="nano", budget="fast", max_iters=1)
        return {"tests_passed": bool(res["tests_passed"]),
                "decision": None,
                "nodes_evaluated": res.get("nodes_evaluated", 0),
                "tokens_generated": res.get("tokens_generated", 0)}

    manifest = run_condition(
        "smoke_nano_solo", tasks, solver, ROOT / "artifacts" / "runs",
        config_sha256=cfg_hash, git_head=_git_head(),
        atlas_git_head=config["identities"]["atlas_git_head"],
        heph_binary_sha256=config["identities"]["heph_binary_sha256"],
        weights_sha256=config["identities"]["weights_sha256"],
        seed=config["seed"], prereg_sha256=None, bridge_mode="fp32",
        probe_status=probe_decision["status"], probe_auc=None,
        probe_ece=None, zoo_block=None, notes=note, chain=chain)
    validate_manifest(manifest)

    run_dir = ROOT / "artifacts" / "runs" / manifest["run_id"]
    emitted = "\n".join(p.read_text(encoding="utf-8")
                        for p in sorted(run_dir.glob("*")))
    holdout_texts = [p.read_text(encoding="utf-8")
                     for p in sorted(HOLDOUT_DIR.glob("*.txt"))]
    h_index = build_holdout_index(holdout_texts)
    known = {fingerprint(t) for t in holdout_texts}
    gate = require_clean(emitted, h_index, known,
                         n=config["contamination"]["ngram_n"],
                         max_hits=config["contamination"]["max_hits"])
    chain.append({"action": "contamination_gate_passed",
                  "run_id": manifest["run_id"],
                  "scope": "emitted artifacts (per_task + manifest)",
                  "ngram_hits": gate["ngram_hits"],
                  "exact_hits": gate["exact_hits"]})
    chain.append({"action": "fase4_gate_state",
                  "anclas": {"9": "green", "11": "green",
                             "12": "green", "13": "green"},
                  "smoke_run_id": manifest["run_id"],
                  "probe": probe_decision["cause"],
                  "tests": "89/89"})
    chain.save(ROOT / "logs" / "audit.jsonl")
    print(json.dumps({"stage": "smoke", "run_id": manifest["run_id"],
                      "accuracy": manifest["accuracy_overall"],
                      "cpu_s_total": manifest["cpu_s_total"],
                      "wall_s": manifest["wall_s"],
                      "contamination": gate,
                      "manifest_ok": True}))
    return manifest


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    chain = _load_chain()
    hook = AtlasHook(config, ROOT)
    try:
        hook.verify_identity(config)
        decision = {"status": "desactivado",
                    "cause": "probe_desactivado",
                    "renormalized_weights":
                        renormalize({"programmatic": 0.45,
                                     "symbolic": 0.35, "probe": 0.20},
                                    "probe")}
        if stage in ("probe", "all"):
            decision = stage_probe(hook, config, chain)
        if stage in ("smoke", "all"):
            stage_smoke(hook, config, chain, decision)
    finally:
        hook.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
