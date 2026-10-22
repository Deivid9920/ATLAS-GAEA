"""lineage_measured: ronda de linaje bajo G1-G4 medida (FASE 6.b).

Stages (resume-friendly, each idempotent by artifact):
  defs     definiciones operacionales de las metricas registradas y
           encadenadas ANTES de calcular cualquier metrica
  measure  metricas desde artifacts reales + decision G1-G4 producida
           por el codigo de reglas de ATLAS (worker, solo lectura)

The growth ops (merge TIES density 0.7, expand block_stacking) are the
configured ATLAS ops reported with the decision; a gate refusal is a
valid result and is reported with its full checks. gaea_v never
executes growth on a sibling (the evaluator measures, does not
improve).
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
from gv.canon import canonical, sha256_canonical  # noqa: E402
from gv.lin.matching import params_from_tensors  # noqa: E402
from gv.lin.trace_diversity import trace_diversity  # noqa: E402

DEFS_ID = "lineage_defs_20261021"
ART = ROOT / "artifacts" / "lineage_g1g4_round.json"


def _git_head() -> str:
    out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, cwd=str(ROOT))
    return out.stdout.strip() or "uncommitted"


def _chain() -> AuditChain:
    path = ROOT / "logs" / "audit.jsonl"
    c = AuditChain.load(path) if path.exists() else AuditChain()
    ok, bad = c.verify()
    if not ok:
        raise SystemExit(f"audit chain broken at seq {bad}; refusing")
    return c


# -- stage defs -------------------------------------------------------------

def stage_defs(config: dict, chain: AuditChain) -> None:
    out = ROOT / "artifacts" / "prereg" / f"{DEFS_ID}.json"
    if out.is_file():
        print(json.dumps({"stage": "defs", "skipped": "exists"}))
        return
    defs = {
        "defs_id": DEFS_ID,
        "round": "FASE 6.b — ronda de linaje bajo G1-G4",
        "decision_function": "atlas_ns.lineage.rules.decide_expansion "
                             "ejecutada verbatim vía worker (solo "
                             "lectura); umbrales de atlas/config.yaml "
                             "lineage.growth, no re-implementados",
        "metrics": {
            "fail_rate": "1 - accuracy_overall del run bench_atlas "
                         "(escalera 100, budget fast, max_iters 3)",
            "unrecovered_rate": "fracción de la escalera que permanece "
                                "fallida tras el presupuesto MCTS "
                                "completo; bajo esta medición "
                                "post-búsqueda coincide con fail_rate; "
                                "no existe telemetría por-iteración en "
                                "este build",
            "diversity_ratio": "cluster_entropy(respuestas atlas del "
                               "bench) / cluster_entropy(respuestas "
                               "nano_solo del bench) via "
                               "gv.lin.trace_diversity (MinHash)",
            "generations_since_growth": "registros genealógicos desde "
                                        "el último crecimiento según el "
                                        "registro de linaje de ATLAS; "
                                        "no existe registro genealógico "
                                        "(nunca hubo crecimiento "
                                        "registrado) → 0",
            "params_current": "suma de las formas de tensores de "
                              "hephaestus/artifacts/tensors.tsv "
                              "(params_from_tensors)",
            "audit_ok": "verify() de la cadena gaea_v AND verify() de "
                        "la cadena atlas",
        },
        "planned_data_runs": ["bench_atlas", "bench_nano_solo"],
        "outcome_policy": "un rechazo de gate es un resultado válido y "
                          "se reporta con sus checks completos; los "
                          "ops de crecimiento (merge TIES density 0.7, "
                          "expand block_stacking) solo los ejecutaría "
                          "ATLAS en su propio repo si la decisión "
                          "fuera expand=true — gaea_v nunca modifica "
                          "hermanos",
        "created_utc_excluded_from_hash": True,
    }
    digest = sha256_canonical(defs)
    out.write_text(canonical(dict(defs, artifact_sha256=digest)) + "\n",
                   encoding="utf-8")
    chain.append({"action": "lineage_operational_definitions_registered",
                  "defs_id": DEFS_ID, "artifact_sha256": digest,
                  "registered": "antes de calcular cualquier métrica "
                                "de linaje"})
    chain.save(ROOT / "logs" / "audit.jsonl")
    print(json.dumps({"stage": "defs", "artifact_sha256": digest[:12]}))


# -- stage measure ----------------------------------------------------------

def _atlas_chain_ok() -> bool:
    log = ROOT.parent / "atlas" / "logs" / "audit.jsonl"
    if not log.is_file():
        return False
    ok, _bad = AuditChain.load(log).verify()
    return ok


def _answers(run_id: str) -> list[str]:
    path = ROOT / "artifacts" / "runs" / run_id / "per_task.jsonl"
    rows = [json.loads(l) for l in
            path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if any("solver_answer" not in r for r in rows):
        raise SystemExit(f"run {run_id} lacks solver_answer traces; "
                         "diversity would be fabricated")
    # Empty answers are DATA (a measured empty trace), not missing
    # data: trace_diversity filters them under its frozen contract and
    # the counts are reported next to the ratio.
    return [r["solver_answer"] for r in rows]


def stage_measure(hook: AtlasHook, config: dict, chain: AuditChain) -> None:
    if ART.is_file():
        print(json.dumps({"stage": "measure", "skipped": "exists"}))
        return
    m_atlas_path = ROOT / "artifacts" / "runs" / "bench_atlas" / \
        "manifest.json"
    if not m_atlas_path.is_file():
        raise SystemExit("lineage measure requires the bench_atlas run "
                         "(gate: bench first)")
    m_atlas = json.loads(m_atlas_path.read_text(encoding="utf-8"))
    fail_rate = round(1.0 - m_atlas["accuracy_overall"], 6)

    base = trace_diversity(_answers("bench_nano_solo"))
    round_ = trace_diversity(_answers("bench_atlas"))
    if base["cluster_entropy"] <= 0:
        raise SystemExit("baseline trace entropy is zero; ratio "
                         "undefined — refusing to invent it")
    diversity_ratio = round(round_["cluster_entropy"]
                            / base["cluster_entropy"], 6)
    trace_counts = {"nano_solo": {"n_total": 100,
                                  "n_nonempty": base["n_traces"]},
                    "atlas": {"n_total": 100,
                              "n_nonempty": round_["n_traces"]}}

    params = params_from_tensors(ROOT.parent / "hephaestus" /
                                 "artifacts" / "tensors.tsv")
    ok_self, _bad_self = AuditChain.load(
        ROOT / "logs" / "audit.jsonl").verify()
    atlas_ok = _atlas_chain_ok()
    metrics = {
        "fail_rate": fail_rate,
        "unrecovered_rate": fail_rate,
        "diversity_ratio": diversity_ratio,
        "generations_since_growth": 0,
        "params_current": params,
        "audit_ok": bool(ok_self and atlas_ok),
    }
    sources = {
        "fail_rate": "artifacts/runs/bench_atlas/manifest.json",
        "diversity_ratio": {"baseline_entropy":
                            base["cluster_entropy"],
                            "round_entropy":
                            round_["cluster_entropy"],
                            "trace_counts": trace_counts},
        "params_current": "hephaestus/artifacts/tensors.tsv",
        "generations_since_growth": "registro genealógico de ATLAS "
                                    "inexistente (0 registros)",
        "audit_ok": {"gaea_v": ok_self, "atlas": atlas_ok},
    }
    chain.append({"action": "lineage_metrics_measured",
                  "metrics": metrics, "sources": sources})

    resp = hook.lineage_decide(metrics)
    decision = {"expand": resp["expand"], "causes": resp["causes"],
                "checks": resp["checks"]}
    artifact = {
        "round": "FASE 6.b",
        "created_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "defs_id": DEFS_ID,
        "metrics": metrics, "sources": sources,
        "decision": decision,
        "rules_from": resp["rules_from"],
        "configured_ops": resp["configured_ops"],
        "execution": ("growth NOT executed from gv: expand=true would "
                      "hand the configured ops to ATLAS's own "
                      "governance; the evaluator never modifies a "
                      "sibling") if decision["expand"]
                     else "no_growth_justified (gate refusal is the "
                          "valid result)",
        "measured_utc_run": m_atlas["run_id"],
        "gaea_v_head": _git_head(),
    }
    ART.write_text(json.dumps(artifact, ensure_ascii=False, indent=1)
                   + "\n", encoding="utf-8")
    chain.append({"action": "lineage_decision_registered",
                  "expand": decision["expand"],
                  "causes": decision["causes"],
                  "checks": {k: v["pass"] for k, v in
                             decision["checks"].items()},
                  "artifact_sha256": sha256_canonical(artifact)})
    chain.save(ROOT / "logs" / "audit.jsonl")
    print(json.dumps({"stage": "measure", "expand": decision["expand"],
                      "causes": decision["causes"]}))


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    chain = _chain()
    if stage in ("defs", "all"):
        stage_defs(config, chain)
    if stage in ("measure", "all"):
        hook = AtlasHook(config, ROOT)
        try:
            hook.verify_identity(config)
            stage_measure(hook, config, chain)
        finally:
            hook.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
