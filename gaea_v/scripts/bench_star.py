"""bench_star: bench 3 columnas de ATLAS bajo medición (FASE 6.a).

Stages (resume-friendly, each idempotent by artifact):
  prereg     familia inferencial Anexo B encadenada ANTES de datos
  nano_solo  condicion nano sobre la escalera 100 (sin verificador:
             decision null — fabricar un veredicto esta prohibido)
  atlas      condicion atlas (MCTS+verificador compuesto real)
  inference  UNICA lectura inferencial: HB1 (paired bootstrap por
             task_id, Holm sobre la familia, regla doble)
  h4         eje int8 del verificador: intento mecanico y veredicto
             de retenccion no medible con causa (6.e)
  doc        docs/bench_code_qa.md generado SOLO de manifiestos

The third column (cloud_reference) stays null: no external API runs
without explicit operator approval (no-go), so it is declared, never
measured.
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
from gv.canon import (canonical, config_sha256, sha256_canonical,  # noqa: E402
                      sha256_file)
from gv.stats.prereg import emit_prereg, prereg_hash  # noqa: E402
from gv.stats.stats_core import holm, paired_bootstrap  # noqa: E402
from gv.harness.efficiency_manifest import validate_manifest  # noqa: E402
from gv.harness.runner import run_condition  # noqa: E402
from gv.harness.task_ladder import load_ladder, suite_digest  # noqa: E402

PREREG_ID = "prereg_20261021_bench_3col"
RUN_NANO = "bench_nano_solo"
RUN_ATLAS = "bench_atlas"
ANSWER_CAP = 2000


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


def _save_chain(chain: AuditChain) -> None:
    chain.save(ROOT / "logs" / "audit.jsonl")


def _run_manifest(run_id: str) -> dict | None:
    p = ROOT / "artifacts" / "runs" / run_id / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() \
        else None


# -- stage prereg ----------------------------------------------------------

def stage_prereg(config: dict, tasks: list, chain: AuditChain) -> str:
    existing = ROOT / "artifacts" / "prereg" / f"{PREREG_ID}.json"
    if existing.is_file():
        digest = prereg_hash(json.loads(
            existing.read_text(encoding="utf-8")))
        print(json.dumps({"stage": "prereg", "skipped": "exists",
                          "prereg_sha256": digest}))
        return digest
    champion = json.loads((ROOT / "artifacts" / "champion_tag.json")
                          .read_text(encoding="utf-8"))
    prereg = {
        "prereg_id": PREREG_ID,
        "suite_digest": suite_digest(tasks),
        "config_sha256": config_sha256(ROOT / "config.yaml"),
        "champion_tag_sha256": sha256_canonical(champion),
        "pilot_usage": "none",
        "epsilon_equivalence": None,
        "epsilon_derivation": {
            "method": "not_applicable_no_equivalence_test",
            "n": config["suite"]["n_total"],
            "power_target": None, "seed": config["seed"]},
        "family_hypotheses": [
            {"id": "HB1",
             "claim": "atlas > nano_solo (accuracy sobre la escalera "
                      "100, bench FASE 6, presupuesto fast/max_iters "
                      f"{config['pilot']['max_iters']})",
             "test": "paired_bootstrap", "direction": "superiority",
             "data_runs": [RUN_ATLAS, RUN_NANO],
             "pairing": "task_id"}],
        "claim_rule": "p_holm<0.05 AND ci_excludes_0",
        "excluded_patterns_contamination": [],
        "interim_monitoring": "allowed, no claims",
        "cloud_reference": None,
        "cloud_reference_cause": "sin APIs externas ni nube en las "
                                 "mediciones (no-go vinculado); la "
                                 "columna se declara, no se mide",
    }
    path, digest = emit_prereg(prereg, chain,
                               ROOT / "artifacts" / "prereg")
    _save_chain(chain)
    print(json.dumps({"stage": "prereg", "path": str(path),
                      "prereg_sha256": digest}))
    return digest


# -- stages nano_solo / atlas ----------------------------------------------

def _solver(hook: AtlasHook, mode: str, config: dict):
    def solve(task: dict) -> dict:
        res = hook.solve(task, mode=mode,
                         budget=config["pilot"]["budget"],
                         max_iters=config["pilot"]["max_iters"],
                         answer_cap=ANSWER_CAP)
        row = {"tests_passed": bool(res["tests_passed"]),
               "decision": res.get("decision"),
               "nodes_evaluated": res.get("nodes_evaluated", 0),
               "tokens_generated": res.get("tokens_generated", 0)}
        if "answer" in res:
            row["answer"] = res["answer"]
        return row
    return solve


def stage_run(hook: AtlasHook, config: dict, tasks: list,
              chain: AuditChain, mode: str) -> str:
    cond = "nano_solo" if mode == "nano" else "atlas"
    run_id = RUN_NANO if mode == "nano" else RUN_ATLAS
    if _run_manifest(run_id) is not None:
        print(json.dumps({"stage": "run", "condition": cond,
                          "skipped": "run exists"}))
        return run_id
    prereg = prereg_hash(json.loads(
        (ROOT / "artifacts" / "prereg" / f"{PREREG_ID}.json")
        .read_text(encoding="utf-8")))
    manifest = run_condition(
        cond, tasks, _solver(hook, mode, config),
        ROOT / "artifacts" / "runs", run_id=run_id,
        config_sha256=config_sha256(ROOT / "config.yaml"),
        git_head=_git_head(),
        atlas_git_head=config["identities"]["atlas_git_head"],
        heph_binary_sha256=config["identities"]["heph_binary_sha256"],
        weights_sha256=config["identities"]["weights_sha256"],
        seed=config["seed"], prereg_sha256=prereg,
        bridge_mode="fp32", probe_status="desactivado",
        notes=f"F6 bench 3 columnas: modo {mode}, budget "
              f"{config['pilot']['budget']}, max_iters "
              f"{config['pilot']['max_iters']}, escalera completa "
              f"n={len(tasks)}; veredicto solo de condiciones con "
              f"verificador (decision null en nano_solo); CPU incluye "
              f"el worker vivo via /proc (probe en la misma "
              f"frontera)",
        child_cpu_probe=hook.cpu_seconds,
        chain=chain)
    validate_manifest(manifest)
    _save_chain(chain)
    print(json.dumps({"stage": "run", "condition": cond,
                      "run_id": run_id,
                      "accuracy": manifest["accuracy_overall"],
                      "cpu_s_total": manifest["cpu_s_total"],
                      "nodes": manifest["mcts_nodes_total"]}))
    return run_id


# -- stage inference -------------------------------------------------------

def _per_task_rows(run_id: str) -> list[dict]:
    path = ROOT / "artifacts" / "runs" / run_id / "per_task.jsonl"
    return [json.loads(l) for l in
            path.read_text(encoding="utf-8").splitlines() if l.strip()]


def stage_inference(config: dict, chain: AuditChain) -> None:
    out = ROOT / "artifacts" / "bench_3col_inference.json"
    if out.is_file():
        print(json.dumps({"stage": "inference",
                          "skipped": "final read already exists"}))
        return
    prereg = json.loads((ROOT / "artifacts" / "prereg" /
                         f"{PREREG_ID}.json").read_text(encoding="utf-8"))
    rows_atlas = {r["task"]: r for r in _per_task_rows(RUN_ATLAS)}
    rows_nano = {r["task"]: r for r in _per_task_rows(RUN_NANO)}
    shared = sorted(set(rows_atlas) & set(rows_nano))
    if len(shared) != config["suite"]["n_total"]:
        raise SystemExit(f"paired suite incomplete: {len(shared)}")
    scores_atlas = [int(rows_atlas[t]["tests_passed"]) for t in shared]
    scores_nano = [int(rows_nano[t]["tests_passed"]) for t in shared]
    boot = paired_bootstrap(scores_atlas, scores_nano,
                            config["stats"]["bootstrap_resamples"],
                            config["stats"]["seed"])
    adj = holm([boot["p_two_sided"]])
    p_holm = adj["p_holm"][0]
    ci_excludes_0 = boot["ci_lo"] > 0 or boot["ci_hi"] < 0
    claimed = bool(p_holm < config["stats"]["alpha"]
                   and ci_excludes_0)
    result = {
        "prereg_id": PREREG_ID,
        "prereg_sha256": prereg_hash(prereg),
        "hypothesis": "HB1",
        "claim": prereg["family_hypotheses"][0]["claim"],
        "runs": {"atlas": RUN_ATLAS, "nano_solo": RUN_NANO},
        "n_pairs": len(shared),
        "delta": boot["delta"], "ci_lo": boot["ci_lo"],
        "ci_hi": boot["ci_hi"], "p_two_sided": boot["p_two_sided"],
        "p_holm": p_holm, "ci_excludes_0": ci_excludes_0,
        "claimed": claimed,
        "rule": prereg["claim_rule"],
        "read_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "single_read": "única lectura inferencial de la familia "
                       "(Holm sobre 1 hipótesis); re-lecturas "
                       "prohibidas (S-20)",
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1)
                   + "\n", encoding="utf-8")
    chain.append({"action": "bench_inference_registered",
                  "hypothesis": "HB1", "delta": boot["delta"],
                  "ci": [boot["ci_lo"], boot["ci_hi"]],
                  "p_holm": p_holm, "claimed": claimed,
                  "n_pairs": len(shared)})
    _save_chain(chain)
    print(json.dumps({"stage": "inference", "delta": boot["delta"],
                      "p_holm": p_holm, "claimed": claimed}))


# -- stage h4 (veredictos int8 vs fp32) ------------------------------------

def stage_h4(hook: AtlasHook, config: dict, tasks: list,
             chain: AuditChain) -> None:
    out = ROOT / "artifacts" / "fase6_h4_int8.json"
    if out.is_file():
        print(json.dumps({"stage": "h4", "skipped": "artifact exists"}))
        return
    probe_task = tasks[0]
    attempt = {"action": "hook.generate weights_variant=int8",
               "prompt_sha256": sha256_canonical(probe_task["prompt"])}
    try:
        gen = hook.generate(probe_task["prompt"], max_new_tokens=8,
                            temperature=0.8, weights_variant="int8")
        attempt["result"] = "generated"
        attempt["text_sha256"] = sha256_canonical(gen.get("text", ""))
    except Exception as exc:  # fail-loud captured as the measured cause
        attempt["result"] = "refused"
        attempt["error"] = f"{type(exc).__name__}: {exc}"
    verdict = {
        "metric": "retencion de veredictos del compuesto int8 vs fp32 "
                  "sobre las 100 tareas (FASE 6.e)",
        "status": "not_measurable",
        "cause": "el compuesto de verificacion no tiene eje de "
                 "precision: op_evaluate no acepta bridge_mode, y el "
                 "generador heph de este build es fp32-only (el eje "
                 "int8 quedo declarado no evaluable en FASE 5, evento "
                 "seq 30 h4_not_measurable)",
        "mechanical_attempt": attempt,
        "disposition": "la columna atlas_int8 del Anexo A permanece "
                       "sin medir con causa; F-01 (cuantizacion "
                       "adaptativa) exige zoo en verde antes de "
                       "conmutar precision",
        "registered_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
    }
    out.write_text(json.dumps(verdict, ensure_ascii=False, indent=1)
                   + "\n", encoding="utf-8")
    chain.append({"action": "fase6_h4_verdict_retention",
                  "status": "not_measurable",
                  "mechanical_attempt": attempt["result"],
                  "cause_ref": "seq 30 h4_not_measurable"})
    _save_chain(chain)
    print(json.dumps({"stage": "h4", "status": "not_measurable",
                      "attempt": attempt["result"]}))


# -- stage doc ---------------------------------------------------------------

def _fmt(x, nd=4):
    return "null" if x is None else (round(x, nd) if isinstance(x, float)
                                     else x)


def stage_doc(config: dict, chain: AuditChain) -> None:
    m_nano = _run_manifest(RUN_NANO)
    m_atlas = _run_manifest(RUN_ATLAS)
    if m_nano is None or m_atlas is None:
        raise SystemExit("bench doc requires both run manifests")
    infer = json.loads((ROOT / "artifacts" /
                        "bench_3col_inference.json").read_text(
        encoding="utf-8"))
    h4 = json.loads((ROOT / "artifacts" / "fase6_h4_int8.json")
                    .read_text(encoding="utf-8"))
    contract = json.loads((ROOT / "artifacts" / "policy_contract_v1.json")
                          .read_text(encoding="utf-8"))
    lineage_path = ROOT / "artifacts" / "lineage_g1g4_round.json"
    lineage = json.loads(lineage_path.read_text(encoding="utf-8")) \
        if lineage_path.is_file() else None

    def row(name, m):
        if m is None:
            return (f"| {name} | null | null | null | null | null | "
                    f"null | null |")
        return (f"| {name} | `{m['run_id']}` | {m['accuracy_overall']} "
                f"| {m['accuracy_by_tier']['t1']} / "
                f"{m['accuracy_by_tier']['t2']} / "
                f"{m['accuracy_by_tier']['t3']} "
                f"| {m['mcts_nodes_total']} | {m['cpu_s_total']} "
                f"| {_fmt(m['accuracy_per_cpu_s'])} "
                f"| {m['mcts_nodes_per_s']} |")

    lines = [
        "# bench_code_qa.md — bench 3 columnas (FASE 6 medida)",
        "",
        "Generado por `scripts/bench_star.py` a partir de manifiestos "
        "reales; cero números a mano (cada cifra lleva run_id). Suite "
        f"congelada digest `{m_atlas['suite_digest'][:12]}…`, "
        f"n_tasks {m_atlas['n_tasks']}, seed {m_atlas['seed']}, "
        f"budget {config['pilot']['budget']}, max_iters "
        f"{config['pilot']['max_iters']}.",
        "",
        "## Columnas",
        "",
        "| condición | run_id | precisión | t1/t2/t3 | nodos MCTS | "
        "CPU-s total | precisión/CPU-s (métrica estrella) | nodos/s |",
        "|---|---|---|---|---|---|---|---|",
        row("nano_solo", m_nano),
        row("atlas", m_atlas),
        row("cloud_reference", None),
        "",
        "La columna cloud_reference es **null**: sin APIs externas ni "
        "nube en las mediciones (no-go vinculado). La fila se declara "
        "null para mantener las 3 columnas del contrato; no existe "
        "corrida cloud ni número cloud.",
        "",
        "## Métrica estrella: precisión/CPU-segundo",
        "",
        f"- atlas: {m_atlas['accuracy_overall']} precisión en "
        f"{m_atlas['cpu_s_total']} CPU-s → "
        f"{_fmt(m_atlas['accuracy_per_cpu_s'])} precisión/CPU-s "
        f"(run `{m_atlas['run_id']}`).",
        f"- nano_solo: {m_nano['accuracy_overall']} precisión en "
        f"{m_nano['cpu_s_total']} CPU-s → "
        f"{_fmt(m_nano['accuracy_per_cpu_s'])} (run "
        f"`{m_nano['run_id']}`).",
        "- La comparación de la métrica estrella es descriptiva (razón "
        "a nivel de run sin test pareado registrable por tarea); la "
        "comparación inferencial preregistrada es HB1 (abajo).",
        "",
        "## Inferencia preregistrada (única lectura)",
        "",
        f"- HB1 (atlas > nano_solo): delta {infer['delta']} "
        f"IC95 [{infer['ci_lo']}, {infer['ci_hi']}] "
        f"(bootstrap pareado {config['stats']['bootstrap_resamples']} "
        f"resamples, seed {config['stats']['seed']}, "
        f"n_pares {infer['n_pairs']}); p_holm {infer['p_holm']}; "
        f"regla doble → "
        f"{'AFIRMACIÓN RECLAMADA' if infer['claimed'] else 'NO reclamada'}.",
        f"- Prereg: `{infer['prereg_id']}` "
        f"({infer['prereg_sha256'][:12]}…), encadenado antes de datos.",
        "",
        "## Acuerdo del verificador bajo quantización (H4 / 6.e)",
        "",
        f"- Estado: **{h4['status']}**. {h4['cause']}",
        f"- Intento mecánico: {h4['mechanical_attempt']['result']}"
        f" ({h4['mechanical_attempt'].get('error', 'n/a')}).",
        "- El ppl NO es la métrica aquí; la retención de veredictos no "
        "es medible sin eje int8 en el compuesto. atlas_int8 queda sin "
        "medir con causa (Anexo A lo permite declarado).",
        "",
        "## Ronda de linaje G1-G4 (6.b)",
        "",
    ]
    if lineage is not None:
        lines += [
            f"- Métricas medidas: fail_rate "
            f"{lineage['metrics']['fail_rate']}, unrecovered_rate "
            f"{lineage['metrics']['unrecovered_rate']}, "
            f"diversity_ratio {lineage['metrics']['diversity_ratio']}, "
            f"generations_since_growth "
            f"{lineage['metrics']['generations_since_growth']}, "
            f"params_current {lineage['metrics']['params_current']}, "
            f"audit_ok {lineage['metrics']['audit_ok']}.",
            f"- Decisión (código de reglas de ATLAS, verbatim): "
            f"expand={lineage['decision']['expand']}.",
            f"- Causas: {'; '.join(lineage['decision']['causes']) or 'ninguna'}.",
            f"- Checks completos: "
            f"{json.dumps(lineage['decision']['checks'], ensure_ascii=False)}",
            f"- Ops configuradas (no ejecutadas desde gv): "
            f"{json.dumps(lineage['configured_ops'], ensure_ascii=False)}.",
        ]
    else:
        lines += ["- PENDIENTE: la ronda de linaje aún no se ha medido "
                  "(scripts/lineage_measured.py)."]
    lines += [
        "",
        "## Contrato de política congelado (6.c)",
        "",
        f"- policy_contract v1 GAEA-ready: module_sha256 "
        f"`{contract['module_sha256'][:12]}…`, artifact_sha256 "
        f"`{contract['artifact_sha256'][:12]}…`, conformance "
        f"{contract['conformance']['substrate_id']} "
        f"(conformant={contract['conformance']['conformant']}).",
        "- Un sustrato cualquiera (transformer, Mamba-2, híbrido) que "
        "implemente propose/score/health entra al arnés sin cambios: "
        "el arnés solo consume solvers y los campos GAEA-L ya están "
        "reservados en el manifiesto.",
        "",
        f"Generado: {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
        f"; cadena de auditoría: {len(chain.entries)} eventos "
        f"(make audit-verify).",
        "",
    ]
    doc = ROOT / "docs" / "bench_code_qa.md"
    doc.write_text("\n".join(lines), encoding="utf-8")
    chain.append({"action": "bench_doc_generated",
                  "path": "docs/bench_code_qa.md",
                  "doc_sha256": sha256_file(doc)})
    _save_chain(chain)
    print(json.dumps({"stage": "doc", "path": str(doc)}))


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    chain = _chain()
    tasks = sorted(load_ladder(ROOT / "profiles"),
                   key=lambda t: t["id"])
    if stage in ("prereg", "all"):
        stage_prereg(config, tasks, chain)
    if stage in ("nano_solo", "atlas", "runs", "all"):
        hook = AtlasHook(config, ROOT)
        try:
            hook.verify_identity(config)
            if stage in ("nano_solo", "runs", "all"):
                stage_run(hook, config, tasks, chain, mode="nano")
            if stage in ("atlas", "runs", "all"):
                stage_run(hook, config, tasks, chain, mode="atlas")
        finally:
            hook.close()
    if stage in ("inference", "all"):
        stage_inference(config, chain)
    if stage in ("h4", "all"):
        config2 = yaml.safe_load((ROOT / "config.yaml").read_text(
            encoding="utf-8"))
        hook = AtlasHook(config2, ROOT)
        try:
            hook.verify_identity(config2)
            stage_h4(hook, config2, tasks, chain)
        finally:
            hook.close()
    if stage in ("doc", "all"):
        stage_doc(config, chain)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
