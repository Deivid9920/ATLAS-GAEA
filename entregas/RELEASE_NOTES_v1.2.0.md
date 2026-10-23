# Release v1.2.0 — Lote 3: ronda 2 de protocolo (RFT + linaje) y veredicto CASSANDRA

Fecha: 2026-10-23. Tag `v1.2.0` (anotado) sobre `4582400` (v1.1.0). Historia
lineal: `25bf247 (v1.0) → 1f0e5d8 (v1.0.1) → 3c622cb (v1.0.2) → 4582400
(v1.1.0) → este commit`.

Alcance: (1) re-ejecución de una ronda RFT con preregistro NUEVO antes de
datos vía los wrappers reales de v1.1.0; (2) re-medición de linaje G1-G4 con
defs nuevas encadenadas antes de recalcular; (3) prueba del runtime CASSANDRA
y veredicto de integración. Sin cambios de anclas S-01, sin cambios de
comportamiento en las rutas de ronda 1 (byte-compatibles), sin assets nuevos.

## Protocolo aplicado (preregistro ANTES de datos, en orden)

1. **Puntero de identidad actualizado con enmienda encadenada**:
   `gaea_v/config.yaml` `identities.atlas_git_head: 4427672 → 4582400`
   (4427672 pertenece a la línea histórica previa al re-empaquetado y ya no
   existe en este repo; la ronda 2 se midió contra `4582400`). Evento
   `config_sha256_chained` en la cadena; `config_sha256` nuevo
   `a2217fdfec256d50…`. Identidades S-01 INTACTAS (ver tabla abajo).
2. **Preregistro de la ronda 2 emitido y encadenado ANTES de cualquier
   dato**: `prereg_20261023_rft_ronda2` vía `emit_prereg` (valida esquema,
   estampa `created_utc`, encadena `prereg_registered`). Hash canónico
   encadenado: `5b40149410f94063…` (los manifiestos incrustan ESTE hash, no
   el sha de los bytes del archivo). Familia no inferencial de protocolo:
   R1 (replicación determinista), R2 (replicación del filtro), R3
   (replicación de diversidad); `pilot_usage: none`; sin reclamos de
   promoción.
3. **Tests primero**: 5 tests nuevos de wrappers (ATLAS) y 8 de protocolo de
   ronda (gaea_v) escritos y en verde ANTES de correr la ronda.
4. **Ejecución de la ronda** vía `make rft STAGE=… ROUND=2` / `make lineage
   STAGE=… ROUND=2` (wrappers reales, prereg exigido, exit code propagado).

## Resultados RFT ronda 2 (métricas con su fuente)

| Métrica | Ronda 1 (congelada) | Ronda 2 (esta medición) |
|---|---|---|
| Preregistro | `cf38d994811def7f…` (v2, congelado) | `5b40149410f94063…` (encadenado antes de datos) |
| Candidatos generados | 800 (50 tareas × 16 temperaturas) | 800 (idéntico protocolo; gate de contaminación ok) |
| Aceptados por el filtro compuesto | 0 | **0** |
| Run de evaluación | `6370c75420b7` (accuracy 0.0, wall 20.9s) | `0a165e7bf531` (accuracy 0.0, wall 20.1s) |
| Entropy drop (diversidad) | 0.0 (fuente: first_16_candidates_per_family) | **0.0** (misma fuente, delta 0.0) |

**Checks del prereg (todos sobre datos reales):**

- **R1 — replicación determinista: PASS.** `n_mismatch = 0` sobre las 100
  tareas de la escalera (`tests_passed` por tarea idéntico entre
  `rft_round_1` y `rft_round_2`); el motor es determinista (rng fijo del
  binario, semilla 42).
- **R2 — replicación del filtro: PASS.** 0 aceptados == 0 aceptados; el
  compuesto (programático + simbólico + policy) vuelve a no seleccionar
  ningún candidato; sin entrenamiento y sin pesos fabricados.
- **R3 — replicación de diversidad: PASS.** entropy_drop 0.0 vs 0.0 (delta
  0.0 dentro de la banda ±0.02 declarada).

**Divulgación honesta:** la stage `eval` se invocó dos veces durante la
verificación del exit path; ambos runs quedaron encadenados
(`91fe70340187` y `0a165e7bf531`) — la cadena es append-only. El
`round_manifest.json` de la ronda 2 queda ligado al segundo
(`0a165e7bf531`); los per-task de ambos son idénticos (determinismo).

## Resultados linaje ronda 2 (re-medición G1-G4)

- Defs nuevas registradas y encadenadas ANTES de recalcular cualquier
  métrica: `lineage_defs_20261023` (sha del artefacto `95e8f6fdedc7…`),
  sobre los runs congelados de FASE 7 (`bench_atlas`/`bench_nano_solo`,
  declarados en `planned_data_runs`).
- Métricas: `fail_rate` 0.5 · `unrecovered_rate` 0.5 · `diversity_ratio`
  según bench congelado · `generations_since_growth` 0 · `params_current`
  según `tensors.tsv` · `audit_ok` true.
- **Decisión: `expand = false`, causa `G3: pacing (too soon since last
  growth)`** — repite la decisión de la ronda 1 (FASE 6.b). Un rechazo de
  gate es un resultado válido y se reporta con sus checks completos.

## Cadena de auditoría

- gaea_v: 53 → **65 eventos, `ok: true`, `first_bad_seq: null`** (eventos
  nuevos: config re-hash, prereg_registered, gates de contaminación,
  candidates banked, filter, 2× run_completed + round_completed, defs de
  linaje, métricas y decisión).
- atlas: 9 eventos, `ok: true` (sin cambios).
- **Bridge-check ATLAS 4/4** y **bridge-check gaea_v VERDE** con el puntero
  actualizado (`git_head 4582400`); huellas resueltas en vivo: heph
  `23981267e759028d…`, pesos `499e8c5313f33522…`. Divulgación: commits
  posteriores a este release volverán a hacer fail-loud el drift de head —
  es el diseño (la cadena queda ligada al head de medición).

## Identidades congeladas S-01 — INTACTAS

| Identidad | sha256 (prefijo) |
|---|---|
| Binario `heph` | `23981267e759028d…` |
| Pesos champion `nano_fp32` | `499e8c5313f33522…` |
| Holdout | `127ef76be336d516…` (el archivo se llama por su propio sha256) |

## Suites

- ATLAS: **204/204** (199 de v1.1.0 + 5 de wrappers con rondas).
- GAEA-V: **117/117** (109 de v1.1.0 + 8 de protocolo de ronda 2; el test de
  anclas se enmienda al puntero nuevo, ver ANCHOR_CHANGES gaea_v).
- prometheus-ns: **257/257** (sin cambios de código; los 2
  `test_required_dir_exists` pasan con los directorios runtime presentes).

## Cambios de código (registro)

- `gaea_v/scripts/run_fase5.py`: registro cerrado de rondas
  (`resolve_round`, 1|2), `--round N` en CLI, dir de artefactos por ronda
  (`artifacts/rft/round_2`), run ids sufijados `_r2` para h3/h4 (que quedan
  congelados en FASE 5 y se rechazan con causa en ronda 2), prereg canónico
  encadenado incrustado en manifiestos. Ronda 1 byte-compatible.
- `gaea_v/scripts/lineage_measured.py`: mismo patrón de rondas; defs r2 con
  `note` de re-ejecución; eventos de cadena llevan `round`.
- `atlas/scripts/rft_round.py` / `lineage_round.py` + `Makefile`: `--round`
  con prereg por ronda y fail-loud por ronda no registrada; el stage `defs`
  del linaje es el paso de REGISTRO y no exige preexistencia del archivo
  (medir sin defs sigue siendo exit 2).
- `gaea_v/config.yaml`: puntero de head (enmienda encadenada).
- Tests: `atlas/tests/test_harness_wrappers.py` (ampliado),
  `gaea_v/tests/test_round2_protocol.py` (nuevo),
  `gaea_v/tests/test_structure.py` (puntero enmendado).

## Prueba de CASSANDRA y veredicto de integración

Qué se ejecutó (runtime materializado desde la entrega del operador, fuera
del monorepo):

1. **Suite propia: 42/42 PASS.**
2. **Datos**: `make data` regeneró byte-idénticos los processed (folds
   `227f4bd169d4…`); el cache de activaciones gpt2 de la entrega venía con
   CSVs de solo-header y el chequeo de idempotencia los dio por buenos —
   forzada re-extracción real (6085 enunciados, 24.5/s, capas [2,5,8,11],
   logprobs incluidos).
3. **Probes**: OOF de referencia pre-computado (194,720 filas heredadas)
   reemplazado por re-entrenamiento local (97,360 filas = 16 configs ×
   6085), CV agrupada por entidad, 5 folds.
4. **Scoring en vivo end-to-end**: `probe_score_sentences` auto-ajustó el
   bundle (`artifacts/probes/gpt2_best.joblib`), extrajo activaciones con
   TransformerLens y puntuó 6 enunciados de verdad conocida fuera de
   dominio: **5/6 de acuerdo** con la etiqueta (scores 0.12–0.99,
   calibrados en la dirección esperada).
5. **Bridge de ATLAS**: con CASSANDRA como hermano, `ProbeVerifier.status()`
   → `{"available": true, "artifacts": ["gpt2_best.joblib", …]}`;
   `verify()` → voto NEUTRAL 0.5 con evidencia honesta ("live scoring lands
   with the CASSANDRA runtime"); `recalibrate(nano_fp32)` → detecta el hash
   `499e8c53…` y encola (`status: queued`). El árbol del monorepo NO quedó
   modificado por esta prueba (el hermano se retiró tras el test).

**Hallazgos (para el lote de integración):**

- El chequeo de idempotencia de `extract_activations` trata un CSV
  solo-header como "cache completo" (falla silenciosa donde debe ser
  fail-loud).
- La entrega no incluye los pesos de probes desplegables
  (`artifacts/probes/` vacío; el bundle se auto-ajusta en la primera
  invocación de scoring) ni logprobs gpt2 (se regeneraron).
- `docs/ensemble_table.md` no publica `tau*` en el formato que el parser
  del bridge de ATLAS espera (`_tau_star()` → None). El voto es NEUTRAL con
  o sin tau*, honesto en ambos casos.

**Veredicto:** CASSANDRA está VIVO y su contrato con ATLAS es real: la
adición al monorepo es viable y se recomienda como **lote 4** dedicado
(cableado del runtime como hermano versionado, corrección del chequeo de
idempotencia, publicación de `tau*` en `ensemble_table.md` y decisión de
alcance: repo completo vs. código+contratos). El probe sigue declarado
`desactivado` en las mediciones hasta que ese lote aterrice.

## Assets

**Sin assets nuevos.** Los artefactos congelados siguen en el Release v1.0
y NO se regeneran. "Un clone fresco funciona" sigue siendo literalmente
cierto en `main`.

## Pendientes declarados (Lote 4, por definir)

- Integración CASSANDRA al monorepo (veredicto arriba).
- Activación de `isolation: netns` en el despliegue del operador (WSL2).
