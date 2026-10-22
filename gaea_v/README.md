# GAEA-VERIFICADOR (gaea_v)

Capa de medición del ecosistema PROMETHEUS-NS / PROMETHEUS-V2 /
HEPHAESTUS / CASSANDRA / ATLAS / GAEA. Es un evaluador estadístico de
ATLAS y un arnés de comparación de sustratos para GAEA.

Principio rector: el evaluador mide; no mejora. Ningún número sin
run_id. Ningún sensor ausente tratado como conforme. Ningún sensor
descalibrado tratado como neutral.

## Qué produce

1. La biblioteca estadística única del ecosistema (gv/stats): bootstrap
   pareado, Holm, TOST, Wilson, ECE, AUC, épsilon derivado de potencia.
2. La escalera de tareas code_qa n=100 (T1=50 importadas de ATLAS,
   T2=30 mutación compuesta, T3=20 adversarias), congelada por digest.
3. El zoo de hackers (30 ataques, 6 categorías) con ZOO_BASELINE y la
   regla de regresión del verificador compuesto de ATLAS.
4. Las FASES 5 y 6 de ATLAS ejecutadas y medidas bajo medición
   certificable (RFT ronda 1 y bench 3 columnas); la FASE 7 de ATLAS
   queda declarada PENDIENTE con causa (ver tabla). Lo no medido se
   declara, nunca se implícita.

## Measured metrics

Todo número de esta tabla proviene de un manifiesto en el repo; la
columna Fuente cita el run_id o artefacto que lo respalda. Lo no
medido dice PENDIENTE con causa. Regla de reclamación usada en toda
inferencia: p_holm < 0.05 AND IC excluye 0 (doble condición, S-20:
una sola lectura inferencial por familia).

| Fase | Métrica | Valor | Fuente (run_id / artefacto) |
|---|---|---|---|
| -1 | Tests de ATLAS reproducidos en este entorno | 165/165 PASSED | evento `fase_minus1_baseline` en logs/audit.jsonl; docs/METRICS_baseline.md |
| -1 | Identidad por huellas congeladas (prompt, heph, champion, holdout, HEAD ecb494b) | 5/5 sha256 OK | evento genesis + `make bridge-check` (5/5) |
| 2 | Escalera congelada n=100 (T1 50 / T2 30 / T3 20) | suite_digest `e775280aa94ef6e2...17bff4` | profiles/code_qa/suite_manifest.json (evento suite_frozen) |
| 2 | Piloto nano_solo accuracy overall (T1/T2/T3) | 0.0 (0.0/0.0/0.0) | run `pilot-pilot_nano_solo-18f52267`, manifest.json |
| 2 | Piloto atlas accuracy overall (T1/T2/T3) | 0.5 (1.0/0.0/0.0) | run `pilot-pilot_atlas-18f52267`, manifest.json |
| 2 | Épsilon de equivalencia (varianza piloto 0.252525, potencia 0.80, n=100, semilla 42) | 0.15 | artifacts/prereg/prereg_20261020_escalera_piloto.json, encadenado ANTES de datos |
| 3 | ZOO_BASELINE v2: catch_global / fpr_clean | 1.0 / 0.0 (6/6 categorías en 1.0) | artifacts/zoo_baseline.json (evento zoo_baseline_frozen; re-lectura tras S-08 con atlas 4427672; ronda inicial 0.8333 FAIL quedó registrada honesta en commit d131f68) |
| 4 | Probe calibrado con decisión (neutral 0.5 prohibido) | 200 ejemplos sandbox; status `desactivado`, pesos renormalizados | artifacts/probe/calibration_200.jsonl (evento probe_calibrado) |
| 4 | Humo frontera unica: tareas / contaminación | 100 / 0 exactas, 0 ngram | run `048e92241fa8`, manifest.json (evento smoke_run) |
| 5 | RFT ronda 1: candidatos / aceptados | 800 / 0 (training skipped, causa empty_accepted_set) | artifacts/rft/round_1/round_manifest.json + run `6370c75420b7` |
| 5 | H2 poda verificador vs poda aleatoria | delta 0.5, IC [0.4, 0.6], p_holm 0.0, RECLAMADA | artifacts/rft/final_inference.json (prereg v2 `cf38d994...` encadenado antes de datos) |
| 5 | H3 verificador compuesto vs baseline | delta 0.25, IC [0.17, 0.34], p_holm 0.0, RECLAMADA | artifacts/rft/final_inference.json |
| 5 | H1 auto-mejora neta | delta 0.0, p_holm 1.0, NO reclamada | artifacts/rft/final_inference.json |
| 5 | H4 int8 retención de veredictos | no_evaluable con causa (eje int8 sin soporte en este build) | evento seq 30 h4_not_measurable; artifacts/fase6_h4_int8.json |
| 6 | Bench nano_solo: accuracy / CPU-s / nodos | 0.0 / 22.8582 / 0 | run `bench_nano_solo`, manifest.json |
| 6 | Bench atlas: accuracy / CPU-s / nodos (nodos/s) | 0.5 / 245.6482 / 800 (3.26 nodos/s) | run `bench_atlas`, manifest.json |
| 6 | HB1 atlas > nano_solo (n_pairs 100) | delta 0.5, IC [0.4, 0.6], p_holm 0.0, RECLAMADA | artifacts/bench_3col_inference.json (prereg_20261021_bench_3col, sha256 `421d8e88...` encadenado antes de datos) |
| 6 | cloud_reference (columna declarada, no-go de nube) | null | prereg_20261021_bench_3col.json (campo cloud_reference_cause) |
| 6 | Linaje G1-G4: fail_rate / unrecovered / diversity_ratio | 0.5 / 0.5 / 1.532069 | artifacts/lineage_g1g4_round.json (defs `lineage_defs_20261021` encadenadas antes de datos) |
| 6 | Decisión de expansión G1-G4 | expand=false, causa G3 pacing | artifacts/lineage_g1g4_round.json (evento lineage_decision_registered) |
| 6 | Columna atlas_int8 del Anexo A | not_measurable con causa mecánica (intento `hook.generate weights_variant=int8` refused) | artifacts/fase6_h4_int8.json |
| 7 | Suite propia de gaea_v (clon fresco) | 108/108 PASSED | `make test` (reproducible; paso 2 del Anexo E) |

PENDIENTES declarados con causa (nunca implícitos):

- FASE 7 de ATLAS: PENDIENTE. Causa: pertenece al prompt maestro y a
  los gates de ATLAS; esta entrega cierra la capa de medición que esa
  fase requiere, no la fase misma.
- Columna cloud_reference de todas las tablas: null. Causa: no-go
  vinculante (sin APIs externas ni nube en las mediciones).
- Columna atlas_int8: sin medir. Causa mecánica registrada en
  artifacts/fase6_h4_int8.json; F-01 exige zoo en verde antes de
  conmutar precisión.

## Uso

    make test           # suite completa (anclas congeladas)
    make audit-verify   # cadena de auditoría logs/audit.jsonl
    make bridge-check   # identidad del puente a ATLAS/HEPHAESTUS
    make pilot          # piloto n=100 -> varianza -> épsilon -> prereg
    make eval           # una condición sobre la escalera
    make zoo            # zoo de hackers -> ZOO_BASELINE
    make rft            # RFT medido (FASE 5)
    make bench          # bench 3 columnas + linaje (FASE 6)
    make package        # empaquetado FASE 7 + SHA256SUMS_GAEA_V.txt

## Entrega y verificación externa (Anexo E)

El paquete es gaea_v_entrega.zip sin .venv, con .gitkeep en todo
directorio vacío y con artifacts/, logs/ y profiles/ como evidencia.
SHA256SUMS_GAEA_V.txt cubre 4 entregables: repo (zip), artefactos
(champion_tag.json), METRICS (docs/METRICS_baseline.md) y manifiesto
(profiles/code_qa/suite_manifest.json). El resultado de la
auto-verificación externa (los 8 pasos del auditor) queda en
docs/ANEXO_E_verificacion_externa.md.

## Identidades congeladas (config.yaml)

Champion nano fp32 (sha256 499e8c53...), binario heph
(23981267...), holdout (digest 62d8992a3add..., archivo
127ef76be336...), ATLAS HEAD 4427672 (enmienda registrada en
docs/ANCHOR_CHANGES.md antes de datos). Cambiar cualquiera de ellas
exige re-baseline completo y prereg nuevo.
