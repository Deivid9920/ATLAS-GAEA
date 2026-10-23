"""run_fase5: FASE 5 — rondas RFT medidas + protocolos H3/H4.

Stages (resume-friendly, each idempotent by artifact):
  h3          podas emparejadas (verifier vs random) sobre 30 T1
  h4          nano fp32 vs int8 sobre las mismas 30 T1
  candidates  16 candidatos por tarea del corpus_rft (heph generate,
              temperatura 0.50..1.25 paso 0.05, rng fijo del binario)
  filter      veredicto del compuesto real (con policy) + sandbox;
              aceptado = approve AND tests_passed
  eval        ronda 1 sobre las 100 tareas (frontera unica)
  diversity   MinHash sobre trazas baseline vs ronda

Every inferential condition carries prereg_sha256 =
6c4f0e0ea302833f26bbc57cc11aa248c138c8c88d7071208e8e0867f485d3c7
(prereg_20261020_rft_rondas). Contamination gates run over every
banked text set; a single hit kills the stage (fail-loud).
"""
from __future__ import annotations

import hashlib
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
from gv.lin.trace_diversity import trace_diversity  # noqa: E402
from gv.stats.prereg import prereg_hash  # noqa: E402

BASE = ROOT.parent
HOLDOUT_DIR = BASE / "prometheus-ns" / "data_clean" / "holdout"
CORPUS = BASE / "atlas" / "artifacts" / "selfplay" / "corpus_rft.jsonl"
RFT_DIR = ROOT / "artifacts" / "rft" / "round_1"
ROUND1_PREREG = "cf38d994811def7ff080a134283d501637512340fa23b0dcd8ff491b765303c7"
ROUND2_PREREG_REL = "artifacts/prereg/prereg_20261023_rft_ronda2.json"
REGISTERED_ROUNDS = (1, 2)
TEMPS = [round(0.50 + 0.05 * i, 2) for i in range(16)]
N_H3_H4 = 100


def resolve_round(n: int) -> dict:
    """Round registry, declared BEFORE any round touches data.

    1 = FASE 5 protocol frozen in v1.0 (byte-compatible: same prereg
    sha, same dirs, same run ids). 2 = protocol re-execution round
    (v1.2.0): new prereg registered in the chain BEFORE data, new
    artifacts dir, run ids suffixed _r2. Unregistered rounds refuse
    with cause — no round is ever improvised."""
    if n not in REGISTERED_ROUNDS:
        raise SystemExit(
            f"ronda no registrada: {n}; registradas: "
            f"{list(REGISTERED_ROUNDS)}")
    if n == 1:
        return {"round": 1, "prereg_sha256": ROUND1_PREREG,
                "rft_dir": RFT_DIR, "suffix": ""}
    p = ROOT / ROUND2_PREREG_REL
    if not p.is_file():
        raise SystemExit(
            f"falta el preregistro de la ronda 2 ({p}) — el preregistro "
            "va ANTES de los datos; no se mide una ronda sin él")
    return {"round": 2,
            # el manifiesto incrusta el hash CANÓNICO encadenado (sin
            # created_utc), el mismo que registró prereg_registered —
            # no el sha de los bytes del archivo
            "prereg_sha256": prereg_hash(
                json.loads(p.read_text(encoding="utf-8"))),
            "rft_dir": ROOT / "artifacts" / "rft" / "round_2",
            "suffix": "_r2"}


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


def _holdout_sets(config: dict) -> tuple[set, set]:
    texts = [p.read_text(encoding="utf-8")
             for p in sorted(HOLDOUT_DIR.glob("*.txt"))]
    return (build_holdout_index(texts,
                                config["contamination"]["ngram_n"]),
            {fingerprint(t) for t in texts})


def _contamination_gate(texts: list, config: dict, chain: AuditChain,
                        scope: str) -> dict:
    index, known = _holdout_sets(config)
    joined = "\n".join(texts)
    grams = ngram_hits(joined, index, config["contamination"]["ngram_n"])
    from gv.contamination.fingerprints import exact_hits
    exact = exact_hits(joined, known)
    if len(grams) > config["contamination"]["max_hits"] or \
            len(exact) > config["contamination"]["max_hits"]:
        chain.append({"action": "contamination_gate_fired",
                      "scope": scope, "ngram_hits": len(grams),
                      "exact_hits": len(exact)})
        chain.save(ROOT / "logs" / "audit.jsonl")
        raise SystemExit(f"contamination in {scope}: "
                         f"{len(grams)} ngram / {len(exact)} exact; "
                         f"stage invalid")
    chain.append({"action": "contamination_gate_passed",
                  "scope": scope, "ngram_hits": len(grams),
                  "exact_hits": len(exact)})
    chain.save(ROOT / "logs" / "audit.jsonl")
    return {"ngram_hits": len(grams), "exact_hits": len(exact),
            "status": "ok"}


def _t1_subset(tasks: list) -> list:
    """Protocolo v2: escalera completa (el esquema Anexo A congela
    n_tasks == 100; la enmienda v2 del prereg sustituye el subconjunto
    de 30 ANTES de ver datos)."""
    return sorted(tasks, key=lambda t: t["id"])


# -- stage h3 ------------------------------------------------------------

def stage_h3(hook: AtlasHook, config: dict, tasks: list,
             chain: AuditChain, only: str | None = None) -> None:
    subset = _t1_subset(tasks)
    for cond, mode in (("h3_poda_verificador", "verifier"),
                       ("h3_poda_aleatoria", "random")):
        # Round-1 frozen protocol; round 2 refuses h3/h4 in main().
        if only and mode != only:
            continue
        run_dir = ROOT / "artifacts" / "runs" / cond
        if (run_dir / "manifest.json").is_file():
            print(json.dumps({"stage": "h3", "condition": cond,
                              "skipped": "run exists"}))
            continue
        out = ROOT / "artifacts" / "runs"

        def solver(task: dict, _mode: str = mode) -> dict:
            res = hook.solve(task, mode="atlas", budget="fast",
                             max_iters=1, prune_mode=_mode)
            return {"tests_passed": bool(res["tests_passed"]),
                    "decision": res.get("decision"),
                    "nodes_evaluated": res.get("nodes_evaluated", 0),
                    "nodes_pruned": res.get("nodes_pruned", 0),
                    "tokens_generated": res.get("tokens_generated", 0)}

        manifest = run_condition(
            cond, subset, solver, out, run_id=cond,
            config_sha256=config_sha256(ROOT / "config.yaml"),
            git_head=_git_head(),
            atlas_git_head=config["identities"]["atlas_git_head"],
            heph_binary_sha256=config["identities"][
                "heph_binary_sha256"],
            weights_sha256=config["identities"]["weights_sha256"],
            seed=config["seed"], prereg_sha256=ROUND1_PREREG,
            bridge_mode="fp32", probe_status="desactivado",
            notes=f"F5 H3 (prereg v2): MCTS prune_mode={mode}, "
                  f"budget fast, max_iters 1, escalera completa "
                  f"n={len(subset)}",
            chain=chain)
        validate_manifest(manifest)
        chain.save(ROOT / "logs" / "audit.jsonl")
        print(json.dumps({"stage": "h3", "condition": cond,
                          "run_id": manifest["run_id"],
                          "accuracy": manifest["accuracy_overall"],
                          "nodes": manifest["mcts_nodes_total"]}))


# -- stage h4 ------------------------------------------------------------

def _extract_code(text: str) -> str:
    if "```" in text:
        parts = text.split("```")
        for part in parts[1::2]:
            body = part.strip()
            if body.startswith("python"):
                body = body[6:]
            if body.strip():
                return body.strip()
    return text.strip()


def stage_h4(hook: AtlasHook, config: dict, tasks: list,
             chain: AuditChain, only: str | None = None) -> None:
    subset = _t1_subset(tasks)
    for variant in ("fp32", "int8"):
        cond = f"h4_nano_{variant}"
        if only and variant != only:
            continue
        run_dir = ROOT / "artifacts" / "runs" / cond
        if (run_dir / "manifest.json").is_file():
            print(json.dumps({"stage": "h4", "condition": cond,
                              "skipped": "run exists"}))
            continue
        texts: list = []

        def solver(task: dict, _v: str = variant) -> dict:
            gen = hook.generate(
                task["prompt"], max_new_tokens=48, temperature=0.8,
                weights_variant=_v)
            text = gen.get("text", "")
            texts.append(text)
            code = _extract_code(text)
            if not code:
                return {"tests_passed": False, "decision": None,
                        "tokens_generated": 0}
            res = hook.run_tests(code, task["tests"])
            return {"tests_passed": bool(res.get("passed")),
                    "decision": None, "tokens_generated": len(text)}

        manifest = run_condition(
            cond, subset, solver, ROOT / "artifacts" / "runs",
            run_id=cond,
            config_sha256=config_sha256(ROOT / "config.yaml"),
            git_head=_git_head(),
            atlas_git_head=config["identities"]["atlas_git_head"],
            heph_binary_sha256=config["identities"][
                "heph_binary_sha256"],
            weights_sha256=config["identities"]["weights_sha256"],
            seed=config["seed"], prereg_sha256=ROUND1_PREREG,
            bridge_mode="fp32" if variant == "fp32" else "int8",
            probe_status="desactivado",
            notes=f"F5 H4 (prereg v2): heph generate "
                  f"weights_variant={variant}, max_new_tokens 48, "
                  f"temperature 0.8, escalera completa n={len(subset)}",
            chain=chain)
        validate_manifest(manifest)
        gate = _contamination_gate(texts, config, chain,
                                   f"{cond}:generated_texts")
        chain.append({"action": "h4_variant_measured",
                      "condition": cond, "run_id": manifest["run_id"],
                      "accuracy": manifest["accuracy_overall"],
                      "contamination": gate})
        chain.save(ROOT / "logs" / "audit.jsonl")
        print(json.dumps({"stage": "h4", "condition": cond,
                          "run_id": manifest["run_id"],
                          "accuracy": manifest["accuracy_overall"]}))


# -- stage candidates -----------------------------------------------------

def stage_candidates(hook: AtlasHook, config: dict, chain: AuditChain,
                     rr: dict | None = None) -> int:
    rr = rr or {"round": 1, "prereg_sha256": ROUND1_PREREG,
                "rft_dir": RFT_DIR, "suffix": ""}
    rft_dir: Path = rr["rft_dir"]
    pool = [json.loads(l) for l in
            CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    rft_dir.mkdir(parents=True, exist_ok=True)
    out_path = rft_dir / "candidates.jsonl"
    if out_path.exists():
        done = {(json.loads(l)["pool_task"],
                 json.loads(l)["temperature"])
                for l in out_path.read_text(encoding="utf-8")
                .splitlines() if l.strip()}
    else:
        done = set()
    with out_path.open("a", encoding="utf-8") as fh:
        for rec in pool:
            for temp in TEMPS:
                if (rec["task"], temp) in done:
                    continue
                gen = hook.generate(rec["prompt"], max_new_tokens=48,
                                    temperature=temp,
                                    weights_variant="fp32")
                fh.write(canonical({
                    "pool_task": rec["task"], "family": rec["family"],
                    "prompt": rec["prompt"], "tests": rec["tests"],
                    "temperature": temp,
                    "text": gen.get("text", "")}) + "\n")
                fh.flush()
    texts = [json.loads(l)["text"] for l in
             out_path.read_text(encoding="utf-8").splitlines()
             if l.strip()]
    gate = _contamination_gate(texts, config, chain,
                               f"rft_round_{rr['round']}:candidates")
    chain.append({"action": "rft_candidates_banked",
                  "round": rr["round"], "n_candidates": len(texts),
                  "n_pool_tasks": len(pool), "temps": TEMPS,
                  "contamination": gate})
    chain.save(ROOT / "logs" / "audit.jsonl")
    print(json.dumps({"stage": "candidates", "n": len(texts),
                      "pool": len(pool)}))
    return len(texts)


# -- stage filter ----------------------------------------------------------

def stage_filter(hook: AtlasHook, config: dict, chain: AuditChain,
                 rr: dict | None = None) -> int:
    rr = rr or {"round": 1, "prereg_sha256": ROUND1_PREREG,
                "rft_dir": RFT_DIR, "suffix": ""}
    rft_dir: Path = rr["rft_dir"]
    cands = [json.loads(l) for l in
             (rft_dir / "candidates.jsonl").read_text(
                 encoding="utf-8").splitlines() if l.strip()]
    accepted: list = []
    rows: list = []
    for c in cands:
        code = _extract_code(c["text"])
        verdict = None
        passed = False
        if code:
            res = hook.run_tests(code, c["tests"])
            passed = bool(res.get("passed"))
            v = hook.evaluate(code, c["tests"], [])
            verdict = v.get("decision")
        rows.append({"pool_task": c["pool_task"],
                     "temperature": c["temperature"],
                     "tests_passed": passed, "verdict": verdict})
        if passed and verdict == "approve":
            accepted.append(dict(c, code=code))
    (rft_dir / "filter_rows.jsonl").write_text(
        "\n".join(canonical(r) for r in rows) + "\n", encoding="utf-8")
    (rft_dir / "accepted.jsonl").write_text(
        "\n".join(canonical(a) for a in accepted) + "\n",
        encoding="utf-8")
    if accepted:
        _contamination_gate([a["text"] for a in accepted], config,
                            chain, f"rft_round_{rr['round']}:accepted")
    fps = sorted({fingerprint(a["code"]) for a in accepted})
    (rft_dir / "corpus_fps.json").write_text(
        json.dumps({"round": rr["round"], "fingerprints": fps}) + "\n",
        encoding="utf-8")
    chain.append({"action": "rft_filter_completed",
                  "round": rr["round"], "n_candidates": len(cands),
                  "n_accepted": len(accepted),
                  "corpus_fps": len(fps)})
    chain.save(ROOT / "logs" / "audit.jsonl")
    print(json.dumps({"stage": "filter", "candidates": len(cands),
                      "accepted": len(accepted)}))
    return len(accepted)


# -- stage eval (ronda 1 sobre la escalera) --------------------------------

def stage_eval(hook: AtlasHook, config: dict, tasks: list,
               chain: AuditChain, rr: dict | None = None) -> str:
    rr = rr or {"round": 1, "prereg_sha256": ROUND1_PREREG,
                "rft_dir": RFT_DIR, "suffix": ""}

    def solver(task: dict) -> dict:
        res = hook.solve(task, mode="nano", budget="fast", max_iters=1)
        return {"tests_passed": bool(res["tests_passed"]),
                "decision": None,
                "nodes_evaluated": res.get("nodes_evaluated", 0),
                "tokens_generated": res.get("tokens_generated", 0)}

    manifest = run_condition(
        f"rft_round_{rr['round']}", sorted(tasks, key=lambda t: t["id"]),
        solver, ROOT / "artifacts" / "runs",
        config_sha256=config_sha256(ROOT / "config.yaml"),
        git_head=_git_head(),
        atlas_git_head=config["identities"]["atlas_git_head"],
        heph_binary_sha256=config["identities"]["heph_binary_sha256"],
        weights_sha256=config["identities"]["weights_sha256"],
        seed=config["seed"], prereg_sha256=rr["prereg_sha256"],
        bridge_mode="fp32", probe_status="desactivado",
        notes=f"F5 ronda {rr['round']}: evaluacion de la escalera con el "
              "champion vigente; entrenamiento veredicto en round_manifest "
              "(cause registrado); seeds declarados 101/202/303",
        chain=chain)
    validate_manifest(manifest)
    chain.save(ROOT / "logs" / "audit.jsonl")
    print(json.dumps({"stage": "eval", "run_id": manifest["run_id"],
                      "accuracy": manifest["accuracy_overall"]}))
    return manifest["run_id"]


# -- stage diversity + round manifest --------------------------------------

def stage_diversity(config: dict, chain: AuditChain, eval_run_id: str,
                    rr: dict | None = None) -> None:
    rr = rr or {"round": 1, "prereg_sha256": ROUND1_PREREG,
                "rft_dir": RFT_DIR, "suffix": ""}
    rft_dir: Path = rr["rft_dir"]
    pool = [json.loads(l) for l in
            CORPUS.read_text(encoding="utf-8").splitlines() if l.strip()]
    accepted_path = rft_dir / "accepted.jsonl"
    accepted = [json.loads(l) for l in
                accepted_path.read_text(encoding="utf-8").splitlines()
                if l.strip()] if accepted_path.exists() else []
    if accepted:
        round_traces = [a["text"] for a in accepted]
        trace_source = "accepted_candidates"
    else:
        cands = [json.loads(l) for l in
                 (rft_dir / "candidates.jsonl").read_text(
                     encoding="utf-8").splitlines() if l.strip()]
        first_by_family: dict = {}
        for c in cands:
            first_by_family.setdefault(c["family"], []).append(c["text"])
        round_traces = [t for fam in sorted(first_by_family)
                        for t in first_by_family[fam][:16]]
        trace_source = "first_16_candidates_per_family (0 accepted)"
    baseline = trace_diversity([r["solution"] for r in pool])
    round_ = trace_diversity(round_traces)
    drop = (1.0 - round_["cluster_entropy"]
            / baseline["cluster_entropy"]) if baseline["cluster_entropy"] \
        > 0 else None
    result = {"baseline": baseline, "round": round_,
              "entropy_drop": round(drop, 4) if drop is not None
              else None, "trace_source": trace_source,
              "ns_rule": "drop > 0.20 blocks promotion"}
    (rft_dir / "diversity.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")

    # training gate (honest scope)
    seeds = config["rft"]["seeds"]
    if accepted:
        train = {"status": "skipped",
                 "cause": "no_trainer_in_gv_scope (LoRA belongs to "
                          "ATLAS FASE 5 infra; rft.py is a declared "
                          "stub); no weights fabricated",
                 "seeds_declared": seeds}
    else:
        train = {"status": "skipped",
                 "cause": "empty_accepted_set (0 candidates survived "
                          "the composite filter)",
                 "seeds_declared": seeds}
    round_manifest = {
        "round": rr["round"], "eval_run_id": eval_run_id,
        "created_utc": datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "prereg_sha256": rr["prereg_sha256"],
        "n_candidates": len(json.loads("[" + ",".join(
            l for l in (rft_dir / "candidates.jsonl").read_text(
                encoding="utf-8").splitlines() if l.strip()) + "]")),
        "n_accepted": len(accepted),
        "diversity": result, "training": train,
        "promotion": "decided at final inference (Holm) with NS "
                     "gates + veto state" if rr["round"] == 1 else
                     "none (ronda de protocolo, prereg sin hipótesis "
                     "de promoción)",
    }
    (rft_dir / "round_manifest.json").write_text(
        json.dumps(round_manifest, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    chain.append({"action": "rft_round_completed", "round": rr["round"],
                  "eval_run_id": eval_run_id,
                  "n_accepted": len(accepted),
                  "cluster_entropy_round": round_["cluster_entropy"],
                  "cluster_entropy_baseline":
                      baseline["cluster_entropy"],
                  "training": train["status"]})
    chain.save(ROOT / "logs" / "audit.jsonl")
    print(json.dumps({"stage": "diversity",
                      "baseline": baseline["cluster_entropy"],
                      "round": round_["cluster_entropy"],
                      "accepted": len(accepted)}))


def main() -> int:
    args = sys.argv[1:]
    round_n = 1
    if "--round" in args:
        i = args.index("--round")
        round_n = int(args[i + 1])
        del args[i:i + 2]
    stage = args[0] if args else "all"
    base, _, only = stage.partition(":")
    rr = resolve_round(round_n)
    if rr["round"] != 1 and base in ("h3", "h4"):
        # h3/h4 belong to the frozen FASE 5 protocol (prereg v2); the
        # re-execution round covers the RFT loop only, as declared in
        # its own prereg.
        raise SystemExit(
            "h3/h4 quedaron congelados en la FASE 5; la ronda 2 cubre "
            "candidates/filter/eval/diversity (prereg "
            "20261023_rft_ronda2)")
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    chain = _chain()
    tasks = sorted(load_ladder(ROOT / "profiles"),
                   key=lambda t: t["id"])
    hook = AtlasHook(config, ROOT)
    try:
        hook.verify_identity(config)
        if base == "h3" or (base == "all" and not only
                            and rr["round"] == 1):
            stage_h3(hook, config, tasks, chain,
                     only=only or None)
        if base == "h4" or (base == "all" and not only
                            and rr["round"] == 1):
            stage_h4(hook, config, tasks, chain,
                     only=only or None)
        if base in ("candidates", "all"):
            stage_candidates(hook, config, chain, rr)
        if base in ("filter", "all"):
            stage_filter(hook, config, chain, rr)
        if base in ("eval", "all"):
            run_id = stage_eval(hook, config, tasks, chain, rr)
            stage_diversity(config, chain, run_id, rr)
    finally:
        hook.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
