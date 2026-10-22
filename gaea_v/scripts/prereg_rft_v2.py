"""prereg_rft_v2: enmienda del protocolo H3/H4 ANTES de ver datos.

Causa: el esquema del manifiesto (Anexo A) congela n_tasks == 100 y
el prereg v1 declaro subconjuntos de 30 tareas T1 para H3/H4. La
comparacion v1 muere SIN haber visto datos (S-20 compatible): ninguna
corrida h3_*/h4_* existia al momento de la enmienda. v2 declara la
escalera completa para H3 y H4. Toda la familia se re-hashea; Holm
corre sobre la familia v2.
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
from gv.canon import config_sha256, sha256_canonical  # noqa: E402
from gv.harness.task_ladder import load_ladder, suite_digest  # noqa: E402
from gv.stats.prereg import emit_prereg  # noqa: E402


def main() -> int:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(
        encoding="utf-8"))
    chain_path = ROOT / "logs" / "audit.jsonl"
    chain = AuditChain.load(chain_path)
    ok, bad = chain.verify()
    if not ok:
        raise SystemExit(f"audit chain broken at seq {bad}; refusing")

    tasks = sorted(load_ladder(ROOT / "profiles"), key=lambda t: t["id"])
    champion = json.loads(
        (ROOT / "artifacts" / "champion_tag.json").read_text(
            encoding="utf-8"))

    prereg = {
        "prereg_id": "prereg_20261020_rft_rondas_v2",
        "supersedes": "prereg_20261020_rft_rondas (muerta sin datos; "
                      "enmienda por esquema Anexo A n_tasks==100)",
        "suite_digest": suite_digest(tasks),
        "config_sha256": config_sha256(ROOT / "config.yaml"),
        "champion_tag_sha256": sha256_canonical(champion),
        "pilot_usage": "variance_only",
        "epsilon_equivalence": 0.15,
        "epsilon_derivation": {
            "n": 100, "variance_pilot": 0.252525, "power_target": 0.80,
            "method": "closed_form_z80_z90", "seed": 42,
            "chained_as": "prereg_20261020_escalera_piloto "
                          "(variance_only; F-2.e)"},
        "family_hypotheses": [
            {"id": "H1",
             "claim": "ronda_final > baseline (accuracy sobre la "
                      "escalera 100; baseline = pilot_nano_solo "
                      "congelado, ronda = rft_round_1)",
             "test": "paired_bootstrap", "direction": "superiority",
             "pairing": "task_id", "data_runs":
                 ["pilot-pilot_nano_solo-18f52267", "rft_round_1"]},
            {"id": "H2",
             "claim": "atlas > nano_solo re-baselined (accuracy sobre "
                      "la escalera 100)",
             "test": "paired_bootstrap", "direction": "superiority",
             "pairing": "task_id", "data_runs":
                 ["pilot-pilot_nano_solo-18f52267",
                  "pilot-pilot_atlas-18f52267"]},
            {"id": "H3",
             "claim": "poda_verificador > poda_aleatoria (accuracy, "
                      "escalera completa 100, presupuesto fast "
                      "identico)",
             "test": "paired_bootstrap", "direction": "superiority",
             "pairing": "task_id", "data_runs":
                 ["h3_poda_verificador", "h3_poda_aleatoria"],
             "protocol": "mcts prune_mode verifier vs random, budget "
                         "fast, max_iters 1, escalera completa n=100"},
            {"id": "H4",
             "claim": "acuerdo del pipeline con pesos int8 == fp32 "
                      "(unica axis int8/fp32 del build: generate de "
                      "heph; TOST sobre delta de accuracy)",
             "test": "tost_equivalence", "direction": "equivalence",
             "pairing": "task_id", "data_runs":
                 ["h4_nano_fp32", "h4_nano_int8"],
             "protocol": "nano-solo escalera completa n=100 por "
                         "variante, max_new_tokens 48, temperature "
                         "0.8 identica"},
            {"id": "H5",
             "claim": "diversidad_trazas ronda_final >= 0.80*baseline "
                      "(TOST; baseline = corpus_rft 50 soluciones "
                      "canonicas; ronda = candidatos aceptados de "
                      "rft_round_1; si 0 aceptados, los 16 primeros "
                      "candidatos por familia; si 0 candidatos, "
                      "no evaluable)",
             "test": "tost_equivalence", "direction": "equivalence",
             "pairing": "trace_set", "data_runs": ["rft_round_1"]}],
        "claim_rule": "p_holm<0.05 AND ci_excludes_0; TOST inside "
                      "epsilon 0.15",
        "excluded_patterns_contamination": [],
        "interim_monitoring": "allowed, no claims",
        "promotion_gates": {
            "double_rule": "p_holm<0.05 AND ci_excludes_0",
            "ns_ppl": "holdout ppl improvement >= 1% on frozen holdout",
            "ns_diversity": "trace diversity drop <= 20%",
            "veto_v2": "probe desactivado (probe_desactivado): veto "
                       "available but absent = round without veto AND "
                       "without promotion"},
        "training_seeds": config["rft"]["seeds"],
        "n_candidates": config["rft"]["n_candidates"],
        "diversity_floor": config["rft"]["diversity_floor"],
    }

    path, digest = emit_prereg(prereg, chain,
                               ROOT / "artifacts" / "prereg")
    chain.append({"action": "prereg_amendment_registered",
                  "from": "prereg_20261020_rft_rondas",
                  "to": "prereg_20261020_rft_rondas_v2",
                  "cause": "Anexo A freezes n_tasks==100; v1 declared "
                           "30-task subsets for H3/H4; amendment "
                           "BEFORE any h3/h4 run (no data seen)",
                  "prereg_sha256": digest})
    chain.save(chain_path)
    print(json.dumps({"prereg": path.name, "prereg_sha256": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
