# bench_code_qa.md — bench 3 columnas (FASE 6 medida)

Generado por `scripts/bench_star.py` a partir de manifiestos reales; cero números a mano (cada cifra lleva run_id). Suite congelada digest `e775280aa94e…`, n_tasks 100, seed 42, budget fast, max_iters 3.

## Columnas

| condición | run_id | precisión | t1/t2/t3 | nodos MCTS | CPU-s total | precisión/CPU-s (métrica estrella) | nodos/s |
|---|---|---|---|---|---|---|---|
| nano_solo | `bench_nano_solo` | 0.0 | 0.0 / 0.0 / 0.0 | 0 | 22.8582 | 0.0 | 0.0 |
| atlas | `bench_atlas` | 0.5 | 1.0 / 0.0 / 0.0 | 800 | 245.6482 | 0.002 | 3.26 |
| cloud_reference | null | null | null | null | null | null | null |

La columna cloud_reference es **null**: sin APIs externas ni nube en las mediciones (no-go vinculado). La fila se declara null para mantener las 3 columnas del contrato; no existe corrida cloud ni número cloud.

## Métrica estrella: precisión/CPU-segundo

- atlas: 0.5 precisión en 245.6482 CPU-s → 0.002 precisión/CPU-s (run `bench_atlas`).
- nano_solo: 0.0 precisión en 22.8582 CPU-s → 0.0 (run `bench_nano_solo`).
- La comparación de la métrica estrella es descriptiva (razón a nivel de run sin test pareado registrable por tarea); la comparación inferencial preregistrada es HB1 (abajo).

## Inferencia preregistrada (única lectura)

- HB1 (atlas > nano_solo): delta 0.5 IC95 [0.4, 0.6] (bootstrap pareado 10000 resamples, seed 42, n_pares 100); p_holm 0.0; regla doble → AFIRMACIÓN RECLAMADA.
- Prereg: `prereg_20261021_bench_3col` (421d8e88c457…), encadenado antes de datos.

## Acuerdo del verificador bajo quantización (H4 / 6.e)

- Estado: **not_measurable**. el compuesto de verificacion no tiene eje de precision: op_evaluate no acepta bridge_mode, y el generador heph de este build es fp32-only (el eje int8 quedo declarado no evaluable en FASE 5, evento seq 30 h4_not_measurable)
- Intento mecánico: refused (BridgeError: atlas op generate failed: RuntimeError: heph generate failed: b'heph generate: safetensors header exceeds file size\n').
- El ppl NO es la métrica aquí; la retención de veredictos no es medible sin eje int8 en el compuesto. atlas_int8 queda sin medir con causa (Anexo A lo permite declarado).

## Ronda de linaje G1-G4 (6.b)

- Métricas medidas: fail_rate 0.5, unrecovered_rate 0.5, diversity_ratio 1.532069, generations_since_growth 0, params_current 13693824, audit_ok True.
- Decisión (código de reglas de ATLAS, verbatim): expand=False.
- Causas: G3: pacing (too soon since last growth).
- Checks completos: {"G1_saturation": {"fail_rate": 0.5, "min_fail_rate": 0.15, "unrecovered_rate": 0.5, "min_unrecovered_rate": 0.05, "pass": true}, "G2_integrity": {"diversity": 1.532069, "floor": 0.8, "audit_ok": true, "pass": true}, "G3_pacing": {"since": 0, "min": 3, "pass": false}, "G4_ceiling": {"params": 13693824, "ceiling": 7000000000.0, "pass": true}}
- Ops configuradas (no ejecutadas desde gv): {"merge": {"method": "ties", "density": 0.7}, "expand": {"method": "block_stacking", "init": "identity"}}.

## Contrato de política congelado (6.c)

- policy_contract v1 GAEA-ready: module_sha256 `06c254b2a61f…`, artifact_sha256 `c56e03e095f2…`, conformance reference_stub (conformant=True).
- Un sustrato cualquiera (transformer, Mamba-2, híbrido) que implemente propose/score/health entra al arnés sin cambios: el arnés solo consume solvers y los campos GAEA-L ya están reservados en el manifiesto.

Generado: 2026-10-20T22:38:34+00:00; cadena de auditoría: 51 eventos (make audit-verify).
