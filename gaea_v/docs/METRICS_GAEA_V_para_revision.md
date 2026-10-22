# METRICS_GAEA_V_para_revision.md — números citables con run_id

Estado al cierre de FASE 7. Cada número existe porque un manifiesto
lo respalda; lo no medido se declara PENDIENTE. La tabla completa
con fuente por celda vive en README.md (sección "Measured metrics");
este doc resume el cierre por fase para revisión externa.

## Baseline (FASE -1)

- ATLAS: 165/165 tests, audit ok, bridge 5/5, humo degenerado
  esperado. Fuente: logs/audit.jsonl de gaea_v (evento
  fase_minus1_baseline) y docs/METRICS_baseline.md.

## Escalera y piloto (FASE 2)

- suite_digest congelado: e775280aa94ef6e2b4918a0785b751d35cbaafc3e
  00fa3610361e3d5cf17bff4 (evento suite_frozen; 50+30+20).
- Piloto: pilot_nano_solo 0.0 (0.0/0.0/0.0 por tier) y pilot_atlas
  0.5 (1.0/0.0/0.0), runs pilot-pilot_nano_solo-18f52267 y
  pilot-pilot_atlas-18f52267. Épsilon 0.15 (var 0.252525, potencia
  0.80, semilla 42) en artifacts/prereg/
  prereg_20261020_escalera_piloto.json, encadenado antes de datos.

## Zoo (FASE 3)

- Ronda inicial honesta: catch_global 0.8333 FAIL (malicious 0.00,
  3 APPROVE) declarada en commit d131f68. Tras corrección S-08 en
  ATLAS (plugin policy, commit 4427672), re-lectura congelada:
  ZOO_BASELINE v2 catch_global 1.0, fpr_clean 0.0, 6/6 categorías.
  Fuente: artifacts/zoo_baseline.json (evento zoo_baseline_frozen).

## FASE 4

- Probe calibrado con decisión en 200 ejemplos sandbox, status
  desactivado con pesos renormalizados (neutral 0.5 prohibido):
  artifacts/probe/calibration_200.jsonl.
- Humo frontera única: 100 tareas, contaminación 0/0, run
  048e92241fa8 (manifiesto Anexo A validado).

## RFT (FASE 5)

- Ronda 1: 800 candidatos, 0 aceptados (training skipped, causa
  empty_accepted_set): artifacts/rft/round_1/round_manifest.json +
  run 6370c75420b7.
- Inferencia final (prereg v2 cf38d994... encadenado antes de
  datos): H2 delta 0.5 IC [0.4,0.6] p_holm 0.0 RECLAMADA; H3 delta
  0.25 IC [0.17,0.34] p_holm 0.0 RECLAMADA; H1 delta 0.0 p_holm 1.0
  NO reclamada; H4 no_evaluable con causa (evento seq 30).
  Fuente: artifacts/rft/final_inference.json.

## Bench y linaje (FASE 6)

- bench_nano_solo: acc 0.0, 22.8582 CPU-s, 0 nodos (run
  bench_nano_solo). bench_atlas: acc 0.5, 245.6482 CPU-s, 800 nodos
  a 3.26 nodos/s (run bench_atlas).
- HB1 (prereg_20261021_bench_3col, 421d8e88..., encadenado antes de
  datos): delta 0.5, IC [0.4,0.6], p_holm 0.0, RECLAMADA, n_pairs
  100, cloud_reference null. Fuente: artifacts/
  bench_3col_inference.json.
- Linaje G1-G4 (defs lineage_defs_20261021 encadenadas antes de
  datos): fail_rate 0.5, unrecovered 0.5, diversity_ratio 1.532069,
  expand=false con causa G3 pacing. Fuente: artifacts/
  lineage_g1g4_round.json.
- atlas_int8: not_measurable con causa mecánica registrada
  (artifacts/fase6_h4_int8.json).

## Entrega (FASE 7)

- README.md sección "Measured metrics": tabla completa con run_id
  por celda, sin placeholders.
- Empaquetado: gaea_v_entrega.zip (sin .venv, .gitkeep garantizado,
  artifacts/logs/profiles como evidencia) + SHA256SUMS_GAEA_V.txt
  (4 hashes: repo, artefactos, METRICS, manifiesto), verificado con
  sha256sum -c.
- Verificación externa: los 8 pasos del Anexo E ejecutados sobre el
  paquete; resultado en docs/ANEXO_E_verificacion_externa.md.

## PENDIENTE declarado

- FASE 7 de ATLAS: PERTENECE al prompt y gates de ATLAS; esta
  entrega cierra la capa de medición que esa fase requiere, no la
  fase misma.
- Columna cloud_reference: null por no-go vinculante de nube.
- Columna atlas_int8: sin medir con causa mecánica registrada.
