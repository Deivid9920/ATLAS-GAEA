# ATLAS + GAEA — Ecosistema de IA verificable

Monorepo del ecosistema **PROMETHEUS-NS / PROMETHEUS-V2 / HEPHAESTUS / CASSANDRA / ATLAS / GAEA-VERIFICADOR**.

Regla de este repositorio: cada número que aparece en cualquier README está respaldado por un manifiesto con `run_id` dentro del árbol. Lo no medido se declara PENDIENTE con su causa, nunca implícito. No hay cifras imputadas.

## Componentes

| Directorio | Qué es | Estado al cierre |
|---|---|---|
| `atlas/` | Agente especialista CPU-only: verificador compuesto (programático + simbólico + probe), presupuesto anytime-compute, cadena de auditoría tamper-evident por acción, protocolo de linaje que solo crece cuando el verificador lo justifica | FASES 0-7 completas · commit `df4eb6f` · tag `v1.0` · suite 204/204 (182 ancla + 5 higiene v1.0.2 + 12 lote 2 v1.1.0 + 5 lote 3 v1.2.0) · `audit-verify` ok |
| `gaea_v/` | GAEA-VERIFICADOR: capa de medición certificable (preregistro antes de datos, corrección de Holm, bootstrap pareado, CPU-segundo con `getrusage`, zoo de ataques anti-hacking congelado) | FASES -1 a 7 con gates verdes · commit `a52277d` · suite 117/117 (108 ancla + 1 higiene v1.0.2 + 8 lote 3 v1.2.0) · Anexo E 8/8 PASS |
| `hephaestus/` | Artefactos de inferencia SIMD C++ congelados por huella sha256 (binario + pesos champion + tokenizer). El código fuente de HEPHAESTUS vive en su propio repositorio | binario `23981267…` · pesos champion `499e8c53…` |
| `prometheus-ns/` | Repositorio base del linaje; aporta `data_clean/holdout` congelado (el archivo se llama por su propio sha256) | holdout `127ef76be336…` verificado |
| `entregas/` | Evidencia de entrega: zips congelados con sus SHA256SUMS, anexo de cierre de FASE 7, informe verificable | zip ATLAS `f17b98dc…` byte-exacto |

## Resultados medidos (resumen)

Fuentes por celda. Detalle completo: `atlas/README.md` y `gaea_v/docs/METRICS_baseline.md`.

| Resultado | Valor | Fuente |
|---|---|---|
| Poda por verificador vs poda aleatoria (FASE 4, 50 tareas) | 200 vs 400 nodos evaluados (-50.0%) | `atlas/artifacts/selfplay/measure_50tasks.json` |
| Bench 3 columnas, 100 tareas: nano solo | 0.0 acc · 22.8582 CPU-s · 0 nodos | `gaea_v/artifacts/runs/bench_nano_solo/manifest.json` |
| Bench 3 columnas, 100 tareas: ATLAS | 0.5 acc (1.00/0.00/0.00 por tier) · 245.6482 CPU-s · 800 nodos | `gaea_v/artifacts/runs/bench_atlas/manifest.json` |
| HB1 (ATLAS > nano, prereg + Holm) | RECLAMADA: delta 0.5, IC [0.4, 0.6], p_holm 0.0 | `gaea_v/artifacts/bench_3col_inference.json` |
| H3 (poda verificador > aleatoria, 100 tareas, 400 nodos) | RECLAMADA: 0.50 vs 0.25, delta 0.25, IC [0.17, 0.34], p_holm 0.0 | runs `h3_poda_verificador` / `h3_poda_aleatoria`; `gaea_v/artifacts/rft/final_inference.json` |
| RFT ronda 1 (honestidad del filtro) | 0/800 candidatos aceptados; entrenamiento omitido, causa `empty_accepted_set` | `gaea_v/artifacts/rft/round_1/round_manifest.json` |
| H1 (auto-mejora neta) | NO reclamada: delta 0.0000, p_holm 1.0 | `gaea_v/artifacts/rft/final_inference.json` |
| H4 / atlas_int8 | NOT_MEASURABLE con causa mecánica (este build de heph genera fp32-only) | `gaea_v/artifacts/fase6_h4_int8.json` |
| Zoo de 30 ataques (regresión anti-hacking) | catch_global 1.00 · fpr_clean 0.00 · 6/6 categorías | `gaea_v/artifacts/zoo_baseline.json` |

## Identidades congeladas (contrato S-01)

Cualquier byte distinto en estas huellas detendría el ecosistema. Verificadas en FASE -1 y re-verificadas por el arnés del Anexo E.

| Ancla | Valor |
|---|---|
| Binario heph | `23981267e759028d71a60d4bf644013c0d09da740c6385435e25e1a5606d3eec` |
| Champion nano fp32 (pesos) | `499e8c5313f33522ba6b300013a177f60dd1fc9001ef2fd67c873aaa34e90190` |
| Holdout (archivo) | `127ef76be336d516bac911bffc68689022361947260a6097ae8df0dac411bbc0` |
| Holdout (digest canónico) | `62d8992a3add265c68990949c7a4100ad412cd4c0b3f4d6f22153280d565d54e` |
| Documento maestro GAEA-V | `ae409daf4898ef10f7cf1f1f9017cfb09dc54fb8394238d0cd70b1b71873f6ca` |
| ATLAS HEAD (FASE 7, tag v1.0) | `df4eb6f` (enmienda S-08 desde `4427672`, desde `ecb494b`) |
| gaea_v (congelado, no regenerado) | `a52277d` |

## Estructura

```
atlas-gaea/
├── atlas/            # agente verificado, FASES 0-7
├── gaea_v/           # capa de medición, FASES -1 a 7
├── hephaestus/       # binario + pesos congelados (LFS para *.safetensors)
├── prometheus-ns/    # base del linaje + holdout congelado
└── entregas/         # zips, SHA256SUMS, anexos, informe verificable
```

Los cuatro proyectos esperan esta disposición de hermanos: `gaea_v/config.yaml` referencia `../atlas`, `../hephaestus` y `../prometheus-ns/data_clean/holdout`; `atlas/config.yaml` referencia `../hephaestus/build/heph`. El monorepo los satisface tal cual, sin ajustes.

## Quickstart

Requisitos: Python 3.10+, `make`, y **git-lfs instalado antes de clonar** (los pesos del champion viajan por LFS; sin git-lfs llegan como puntero y el bridge-check falla por hash — fail-loud, por diseño).

```bash
git lfs install
git clone <este-repo> atlas-gaea && cd atlas-gaea

# ATLAS (los hermanos ../hephaestus y ../gaea_v ya están en su sitio por diseño)
cd atlas
make setup && make bridge-check && make demo   # puente 5/5 + demo
make test                                       # 204/204

# GAEA-VERIFICADOR
cd ../gaea_v
make setup && make test                         # 117/117
make audit-verify                               # cadena íntegra, first_bad_seq null
```

Nota documentada: `make test` de ATLAS añade un registro a `atlas/logs/probe_recalibration.jsonl` (el log es append-only y un test de la suite anexa un registro por corrida). Es comportamiento conocido, registrado en `entregas/ATLAS_fase7_cierre_anexo.md` y con enmienda propuesta en `entregas/PENDIENTES_POST_RELEASE.md`.

## Filosofía de la casa

- **Tests = especificación.** Las anclas no se editan para que pase una implementación; cada desviación está registrada con su justificación en `atlas/docs/ANCHOR_CHANGES.md`.
- **Preregistro antes de datos.** Ninguna afirmación inferencial sin preregistro previo; corrección de Holm; doble condición de reclamación (p_holm < 0.05 AND IC excluye 0).
- **El evaluador mide, no mejora.** GAEA-V es la capa de medición; no optimiza lo que mide.
- **Fail-loud.** Sensor ausente ≠ sensor conforme; un byte alterado en la cadena de auditoría se detecta y localiza (`first_bad_seq`).
- **Cada número con su log.** Toda cifra cita run_id o artefacto; los pendientes se declaran con causa.

## Pendientes declarados (nunca implícitos)

| Pendiente | Causa | Dónde |
|---|---|---|
| Columna `cloud_reference` | null por no-go vinculante de nube; activar exige aprobación explícita del operador | `atlas/config.yaml` (`bench.cloud_reference`), `atlas/docs/no_goals.md` |
| `atlas_int8` | not_measurable: el generador de este build es fp32-only (BridgeError registrada) | `gaea_v/artifacts/fase6_h4_int8.json` |
| Probe CASSANDRA en vivo | Runtime PROBADO en v1.2.0 (42/42 tests, scoring en vivo 5/6 fuera de dominio, bridge `available: true`, recalibrate encola con hash `499e8c53…`); la adición al monorepo queda propuesta como Lote 4 con hallazgos documentados (idempotencia del extract, tau* no publicado en ensemble_table) | `entregas/RELEASE_NOTES_v1.2.0.md` (sección veredicto), `atlas/atlas_ns/verify/plugins/probe.py` |
| Enmienda de higiene de test (#10) | APLICADA en v1.0.2 (fila #13 de ANCHOR_CHANGES) — registro histórico del preregistro | `entregas/PENDIENTES_POST_RELEASE.md` |
| CLIs `make rft` / `make lineage` de ATLAS | RESUELTO en v1.1.0 (ANCHOR_CHANGES #16): wrappers reales que invocan el harness gaea_v (`run_fase5.py` / `lineage_measured.py`) con prereg obligatorio y fail-loud con causa; la re-ejecución produce artefactos NUEVOS y anexa a la cadena de gaea_v | `atlas/scripts/rft_round.py`, `atlas/scripts/lineage_round.py` |
| Activación de `isolation: netns` por despliegue | CAPACIDAD implementada en v1.1.0 (ANCHOR_CHANGES #14): `unshare --net` fail-closed con `no_network_enforced` real; el default de repo sigue siendo `none` (rlimits sin bloqueo de red, reportado honesto) porque hosts sin user namespaces fallarían cerrado — activar `netns` en WSL2/Linux con userns | `atlas/atlas_ns/verify/plugins/programmatic.py`, `atlas/config.yaml` (safety.sandbox.isolation) |

## Entregas y verificación

`entregas/` contiene los zips congelados con sus sumas, el anexo de cierre de FASE 7 (con la salvedad de auditoría registrada al final) y el informe de entrega verificable de 12 páginas.

**Compatibilidad de commits:** las referencias `ecb494b` / `4427672` / `df4eb6f` que aparecen en los artefactos son la misma línea histórica de ATLAS registrada al tiempo de cada medición; la tabla de reconstrucción exacta vive en `gaea_v/docs/COMPATIBILIDAD_COMMITS.md`.

```bash
cd entregas
sha256sum -c SHA256SUMS_ATLAS_entrega.txt   # 4/4 OK con el zip en este directorio
```

Verificación completa estilo Anexo E (8 pasos): extracción fresca del zip, venv nueva, suite completa, `audit-verify`, recomputar huellas con los métodos congelados, manifiestos, marcadores y prueba de manipulación en copia temporal. Procedimiento documentado en `entregas/ATLAS_fase7_cierre_anexo.md`.
