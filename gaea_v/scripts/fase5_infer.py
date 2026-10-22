"""fase5_infer: unica lectura inferencial de FASE 5 (unblinding).

Runs ONCE over the full preregistered family (v2):
  H1, H2, H3 : paired_bootstrap superiority -> Holm over their
               p-values (the TOST hypotheses carry no p; the frozen
               claim rule binds them to "TOST inside epsilon").
  H4         : no evaluable (chained cause BEFORE this reading).
  H5         : TOST over bootstrap-resampled trace-set diversity,
               delta = round_diversity - 0.80 * baseline_diversity,
               epsilon 0.15 (frozen); the NS diversity gate is
               reported alongside.

Promotion decision per the frozen gates; refusal reasons enumerated.
Every number carries its run_id. Output: docs/RFT_MEASURED.md.
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
from gv.canon import canonical  # noqa: E402
from gv.lin.trace_diversity import trace_diversity  # noqa: E402
from gv.stats.stats_core import holm, paired_bootstrap  # noqa: E402

BASE = ROOT.parent
CORPUS = BASE / "atlas" / "artifacts" / "selfplay" / "corpus_rft.jsonl"
RFT_DIR = ROOT / "artifacts" / "rft" / "round_1"
RESAMPLES = 10000
TRACE_RESAMPLES = 2000
SEED = 42
EPSILON = 0.15


def _rows(run_id: str) -> list:
    path = ROOT / "artifacts" / "runs" / run_id / "per_task.jsonl"
    rows = [json.loads(l) for l in path.read_text(
        encoding="utf-8").splitlines() if l.strip()]
    rows.sort(key=lambda r: r["task"])
    return rows


def _scores(run_id: str) -> list:
    return [1 if r["tests_passed"] else 0 for r in _rows(run_id)]


def main() -> int:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    chain = AuditChain.load(ROOT / "logs" / "audit.jsonl")
    ok, bad = chain.verify()
    if not ok:
        raise SystemExit(f"audit chain broken at seq {bad}; refusing")

    nano = _scores("pilot-pilot_nano_solo-18f52267")
    atlas = _scores("pilot-pilot_atlas-18f52267")
    rnd = _scores("6370c75420b7")
    pod_v = _scores("h3_poda_verificador")
    pod_r = _scores("h3_poda_aleatoria")
    assert len(nano) == len(atlas) == len(rnd) == 100

    h1 = paired_bootstrap(rnd, nano, RESAMPLES, SEED)
    h2 = paired_bootstrap(atlas, nano, RESAMPLES, SEED)
    h3 = paired_bootstrap(pod_v, pod_r, RESAMPLES, SEED)
    ps = {"H1": h1["p_two_sided"], "H2": h2["p_two_sided"],
          "H3": h3["p_two_sided"]}
    adj = holm(list(ps.values()))["p_holm"]
    claims = {}
    for hid, res, p_adj in zip(("H1", "H2", "H3"),
                               (h1, h2, h3), adj):
        ci_excludes = (res["ci_lo"] > 0) or (res["ci_hi"] < 0)
        claims[hid] = {"delta": round(res["delta"], 4),
                       "ci": [round(res["ci_lo"], 4),
                              round(res["ci_hi"], 4)],
                       "p": res["p_two_sided"], "p_holm": p_adj,
                       "ci_excludes_0": ci_excludes,
                       "claimed": bool(p_adj < 0.05 and ci_excludes)}

    # H5: TOST over resampled trace-set diversity
    import random
    rng = random.Random(SEED)
    pool = [json.loads(l) for l in
            CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    baseline_traces = [r["solution"] for r in pool]
    cands = [json.loads(l) for l in
             (RFT_DIR / "candidates.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    round_traces = [c["text"] for c in cands]
    deltas = []
    for _ in range(TRACE_RESAMPLES):
        bs = [baseline_traces[rng.randrange(len(baseline_traces))]
              for _ in range(50)]
        rs = [round_traces[rng.randrange(len(round_traces))]
              for _ in range(50)]
        d = trace_diversity(rs)
        b = trace_diversity(bs)
        deltas.append(d["pairwise_diversity"]
                      - 0.80 * b["pairwise_diversity"])
    deltas.sort()

    def pct(q):
        return deltas[min(int(q * (len(deltas) - 1) + 0.5),
                          len(deltas) - 1)]

    lo, hi = pct(0.05), pct(0.95)
    h5 = {"delta_point": round(sum(deltas) / len(deltas), 4),
          "ci90": [round(lo, 4), round(hi, 4)], "epsilon": EPSILON,
          "inside": bool(lo > -EPSILON and hi < EPSILON),
          "floor_holds_point": sum(deltas) / len(deltas) >= 0,
          "note": "pairwise_diversity saturates at 1.0 for sets of "
                  "distinct short traces (measurement ceiling)"}
    div = json.loads((RFT_DIR / "diversity.json").read_text(
        encoding="utf-8"))
    ns_diversity_gate = (div["entropy_drop"] is not None
                         and div["entropy_drop"] <= 0.20)

    # promotion decision (frozen gates)
    reasons = []
    if not claims["H1"]["claimed"]:
        reasons.append("H1 (ronda vs baseline) no supera la regla "
                       "doble: delta "
                       f"{claims['H1']['delta']}, p_holm "
                       f"{claims['H1']['p_holm']}")
    reasons.append("sin entrenamiento (0/800 candidatos aceptados): "
                   "ppl de holdout sin movimiento >= 1%: gate NS ppl "
                   "FALLA")
    reasons.append("veto V2 disponible pero ausente (probe "
                   "desactivado/probe_desactivado): ronda sin veto Y "
                   "sin promocion")
    promotion = {"decision": "refused", "reasons": reasons}

    report = {
        "prereg": "prereg_20261020_rft_rondas_v2",
        "created_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "claims": claims,
        "H4": {"status": "no_evaluable",
               "cause": "chained: h4_not_measurable (heph generate "
                        "is fp32-only in this build)",
               "fp32_arm_run": "h4_nano_fp32"},
        "H5": h5,
        "ns_diversity_gate": {"entropy_drop": div["entropy_drop"],
                              "passes": ns_diversity_gate},
        "promotion": promotion,
        "runs": {
            "baseline_nano": "pilot-pilot_nano_solo-18f52267",
            "baseline_atlas": "pilot-pilot_atlas-18f52267",
            "rft_round_1_eval": "6370c75420b7",
            "h3_verifier": "h3_poda_verificador",
            "h3_random": "h3_poda_aleatoria",
            "h4_fp32": "h4_nano_fp32"},
    }
    (ROOT / "artifacts" / "rft" / "final_inference.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")

    chain.append({"action": "inference_final_registered",
                  "prereg": report["prereg"],
                  "claims": {k: {"p_holm": v["p_holm"],
                                 "claimed": v["claimed"]}
                             for k, v in claims.items()},
                  "H4": "no_evaluable", "H5_inside": h5["inside"]})
    chain.append({"action": "promotion_refused", "round": 1,
                  "reasons": reasons})
    chain.save(ROOT / "logs" / "audit.jsonl")
    print(json.dumps({"claims": {k: v["claimed"]
                                 for k, v in claims.items()},
                      "promotion": promotion["decision"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
