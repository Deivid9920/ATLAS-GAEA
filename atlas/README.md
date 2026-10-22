# ATLAS

The unifying agent of the ecosystem: HEPHAESTUS (C++ SIMD inference) + CASSANDRA
(mechanistic truth probe) + PROMETHEUS-NS/V2 (symbolic graph, lineage) orchestrated into a
narrow, verifiable, private, CPU-only specialist.

## What ATLAS is / is not

**Is**: a domain specialist whose every answer is produced through a composite verifier
(programmatic + symbolic graph + truth probe) under an anytime-compute budget, with a
tamper-evident audit chain per action and a Lineage Protocol that grows the model ONLY when
the verifier justifies it.

**Is not** (§No-goals): a general reasoner; a frontier-model competitor; a trading bot
(autonomous financial trading is an explicitly rejected antipattern — see `docs/no_goals.md`);
a cloud product (zero external LLM APIs in the pipeline).

## Quickstart

```bash
make setup && make bridge-check && make demo
make mcp-serve        # expose atlas.verify to ANY external agent
```

## Measured metrics

Every value below is mechanically measured; each cell cites its run_id and/or
artifact. FASE 4 was measured natively by ATLAS. FASE 5/6 metrics were measured
through the frozen GAEA-VERIFICADOR harness (sibling repo `gaea_v`, read-only,
frozen at a52277d) under preregistered hypotheses with Holm correction and the
double decision rule (p_holm < 0.05 AND CI excluding 0). Anything not measured
is declared PENDING with its cause. No number is imputed.

| Metric | value | source |
|--------|-------|--------|
| Verifier weights / thresholds (anchor) | programmatic 0.45, symbolic 0.35, probe 0.20; tau_approve 0.80, tau_doubt 0.35 | `config.yaml` |
| FASE 4 verification, 50 tasks (nano-solo vs ATLAS) | nano 0.00 vs ATLAS 1.00 accuracy; verifier pruning 200 nodes evaluated vs random pruning 400 (50.0% node reduction) | `artifacts/selfplay/measure_50tasks.json` |
| Audit chain (local) | 9 chained entries, verify ok | `logs/audit.jsonl` (`make audit-verify`) |
| Truth probe | desactivado (decision chained; neutral 0.5 never cited as evidence; every bench manifest carries probe_status="desactivado") | `logs/probe_recalibration.jsonl`; run `bench_atlas` manifest |
| Smoke, 100-task single-frontier (Anexo A) | run `048e92241fa8`: manifest strict-valid, contamination 0 | `gaea_v/artifacts/runs/048e92241fa8/manifest.json` |
| FASE 5 RFT round 1 | 0/800 candidates accepted; training skipped, cause: empty_accepted_set (0 candidates survived the composite filter) | `gaea_v/artifacts/rft/round_1/round_manifest.json` (eval run `6370c75420b7`) |
| H1 (ronda_final > baseline) | NOT claimed: delta 0.0000, CI [0.0000, 0.0000], p_holm 1.0 | `gaea_v/artifacts/rft/final_inference.json` (prereg `prereg_20261020_rft_rondas_v2`) |
| H2 (ATLAS > nano, prereg + Holm) | CLAIMED: delta 0.5, CI [0.4, 0.6], p_holm 0.0 | `gaea_v/artifacts/rft/final_inference.json` |
| H3 (verifier pruning > random pruning; 100 tasks, 400 nodes each) | verifier 0.50 vs random 0.25 accuracy; CLAIMED: delta 0.25, CI [0.17, 0.34], p_holm 0.0 | runs `h3_poda_verificador`, `h3_poda_aleatoria`; `gaea_v/artifacts/rft/final_inference.json` |
| H4 / atlas_int8 | NOT_MEASURABLE with mechanical cause: BridgeError "safetensors header exceeds file size" (this heph build generates fp32-only). fp32 arm run `h4_nano_fp32`: accuracy 0.0 | `gaea_v/artifacts/fase6_h4_int8.json` |
| FASE 6 bench 3-column, nano_solo (100 tasks) | accuracy 0.0, 22.8582 CPU-s, 0 MCTS nodes | run `bench_nano_solo`; `gaea_v/artifacts/runs/bench_nano_solo/manifest.json` |
| FASE 6 bench 3-column, ATLAS (100 tasks) | accuracy 0.5 (1.00/0.00/0.00 by tier), 245.6482 CPU-s, 800 MCTS nodes | run `bench_atlas`; `gaea_v/artifacts/runs/bench_atlas/manifest.json` |
| HB1 (bench, ATLAS > nano_solo; prereg + Holm) | CLAIMED: delta 0.5, CI [0.4, 0.6], p_holm 0.0 | `gaea_v/artifacts/bench_3col_inference.json` (prereg `prereg_20261021_bench_3col`) |
| cloud_reference column | null — PENDING with cause: no-go (zero external LLM APIs by design; activation requires explicit user approval) | `config.yaml` (bench.cloud_reference); `docs/no_goals.md` |
| Lineage round G1-G4 (FASE 6.b) | expand = false; cause: G3 pacing (0 < 3 generations since growth). G1 saturation pass (fail_rate 0.5 >= 0.15), G2 integrity pass (diversity 1.5321 >= 0.80), G4 ceiling pass (13,693,824 params << 7e9) | `gaea_v/artifacts/lineage_g1g4_round.json` (defs `lineage_defs_20261021`) |
| Test suite at delivery | 182/182 PASSED (FASE 7 closure gate; re-run with `make test`) | this package, Anexo E harness on fresh extraction |
