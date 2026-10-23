# Release v1.3.0 — Lote 4: integración de CASSANDRA al monorepo

Fecha: 2026-10-23. Tag `v1.3.0` (anotado) sobre `b708e98` (v1.2.0). Historia
lineal: `3c622cb (v1.0.2) → 4582400 (v1.1.0) → b708e98 (v1.2.0) → este commit`.

Alcance: (1) adición del hermano `cassandra/` como proyecto versionado del
monorepo; (2) corrección de los hallazgos del veredicto v1.2.0 más un defecto
latente nuevo que la integración expuso en el bridge de ATLAS; (3) suite
propia en verde dentro del árbol integrado. Sin cambios de anclas S-01, sin
regeneración de assets congelados, sin force-push.

## Decisión de alcance (repo completo menos regenerables)

Del veredicto v1.2.0 quedaba abierta la decisión "repo completo vs. código +
contratos". Se integró **repo completo menos lo regenerable pesado**, siguiendo
el contrato de `.gitignore` de la propia entrega:

- **Entra**: `cassandra_ns/` (paquete completo), `scripts/` (10 CLIs),
  `tests/` (6 suites heredadas + 2 archivos nuevos), `config.yaml`,
  `Makefile` (contrato de 13 targets intacto), `pyproject.toml`,
  `requirements.txt` + `requirements.freeze.txt`, `README.md`,
  `Dockerfile`, `.gitignore`, `data/processed/folds.json` (ancla
  determinista), `data/external/prometheus_graph.json` (grafo de
  consistencia exportado de PROMETHEUS-NS: 4,442 triplets → 13,225 filas
  de puente), `notebooks/` (5 ejecutados), `docs/ensemble_table.md` +
  `docs/probe_table.md`, y los registros canónicos pequeños de `logs/`
  citados por las docs (ver abajo).
- **No entra** (regenerable, gitignored por la entrega misma): caches de
  activaciones y bundles de probes (`artifacts/*` salvo `.gitkeep`s),
  `data/raw/*` (re-descargable por `make data` con manifiesto sha256 y
  fail-loud), `data/processed` salvo el ancla, figuras PNG, y el resto de
  `logs/` (oof_predictions 35 MB, generaciones, etc.).

Los registros canónicos versionados (`logs/abstention_*.json` con curvas,
`logs/ensemble_results*.json`, `logs/graph_export_stats.json`,
`logs/best_config.json`) siguen el precedente de `folds.json`: cada número
publicado en las docs conserva su manifiesto fuente dentro del árbol, y un
test nuevo lo verifica.

## Hallazgos v1.2.0 → correcciones v1.3.0 (tests primero)

1. **Idempotencia fail-loud** (`cassandra_ns/activations/cache.py` + 2 tests
   de regresión en `tests/test_cache.py`): un índice o un CSV de logprobs
   presente pero sin filas (stub header-only de una primera corrida
   interrumpida) ya no puede consumirse como cache completa. `load_index()`
   y `load_logprobs()` levantan `RuntimeError` con la causa y la remediación;
   `done_ids()` avisa en stderr y conserva la semántica de resume
   (re-extrae todo). El contrato queda documentado en el docstring del
   módulo.
2. **tau* publicado** (`docs/ensemble_table.md` §6 + `tests/test_tau_publication.py`):
   los umbrales de abstención medidos (`gpt2: 0.6447845697402954`,
   `pythia-410m: 0.4648858308792114`) se publican en formato long-row con su
   registro fuente, en el formato exacto que el parser del bridge de ATLAS
   consume (`atlas/atlas_ns/verify/plugins/probe.py`, `_tau_star()`): la
   etiqueta tau y el valor comparten línea. Los tests fijan la igualdad
   exacta publicado-vs-medido para ambos modelos y que todo registro citado
   por la tabla existe en el árbol. Durante la redacción, el propio test
   detectó que el primer formato propuesto (etiqueta en el encabezado,
   valores en filas) NO era parseable por el parser real — se corrigió antes
   de medir nada más, con el parser de producción como árbitro.
3. **Defecto latente del bridge expuesto por la integración** (enmienda #18
   de `atlas/docs/ANCHOR_CHANGES.md`): el filtro de artefactos del probe
   usaba `p.suffix != ".gitkeep"`, que jamás filtra nada (un dotfile tiene
   `Path.suffix == ""`); con el hermano integrado, el stub de contrato
   aparecía como artefacto entrenado fantasma y `status()` mentía
   `available: true, artifacts: ['.gitkeep']`. Corregido a filtro por nombre
   (`p.name != ".gitkeep"`) con test de regresión
   (`test_probe_ignores_gitkeep_stub_artifact`). El voto sigue NEUTRAL en
   ambas ramas; lo que cambia es la honestidad del estado.

## Contrato del puente ATLAS ↔ CASSANDRA (verificado con el código real)

Con el árbol integrado y sin bundles entrenados:

- `ProbeVerifier.status()` → `{"available": false, "reason": "no trained
  probe artifacts", "repo": ".../cassandra"}` — honesto.
- `ProbeVerifier._tau_star()` → `0.6447845697402954` (gpt2, canónico) leído
  desde `cassandra/docs/ensemble_table.md` por el parser de producción.
- `verify()` → voto NEUTRAL 0.5 con evidencia honesta; `recalibrate()`
  intacto (append-only, encola con el hash del modelo).
- El "scoring en vivo 5/6 fuera de dominio" de v1.2.0 requirió un bundle
  auto-ajustado efímero; en el árbol integrado ese paso queda declarado:
  se re-mide con probes propios entrenados vía `make probe` (pendiente
  abajo), nunca se imputa.

## Suites medidas en este árbol (frescas, venv propias)

| Suite | Resultado | Tiempo |
|---|---|---|
| `cassandra/` (nueva) | **47/47** (42 heredadas + 2 regresiones de cache + 3 de publicación tau*) | 4.95s |
| ATLAS | **205/205** (204 + 1 de la enmienda #18) | 23.18s |
| GAEA-V | **117/117** | 13.99s |
| prometheus-ns | **257/257** | 13.71s |

- `audit-verify`: gaea_v **65 ok** / atlas **9 ok**, `first_bad_seq: null`
  en ambos (cadenas íntegras).
- `bridge-check`: ATLAS **verde** con smoke real (`tokenize_canary` 3
  tokens, `generate_smoke` "IGIGIGIGIGIGIGIG"); gaea_v hace fail-loud
  `ATLAS git head drifted: <HEAD> != 4582400` — comportamiento documentado
  desde v1.2.0: la cadena de medición queda ligada al head de medición y
  cualquier commit posterior se reporta honestamente como drift.
- Identidades S-01 recomputadas intactas: heph `23981267…` · nano_fp32
  `499e8c53…` · holdout `127ef76be336…`.
- La suite de CASSANDRA incluye su propio gate anti-marcadores
  (`test_no_ai_markers`) y de árbol requerido (`test_required_tree`),
  ambos en verde sobre el árbol integrado.

## Pendientes declarados (nunca implícitos)

| Pendiente | Causa | Dónde |
|---|---|---|
| Live scoring del probe en ATLAS | Requiere bundle entrenado (`make probe` en `cassandra/`: extracción + CV agrupada); mientras no exista, el voto es NEUTRAL honesto | `cassandra/Makefile`, `atlas/atlas_ns/verify/plugins/probe.py` |
| Cobertura del grafo simbólico | Cero a nivel tupla (hallazgo v1.2.0 se mantiene): corpus técnico/literario vs. generaciones open-domain; corpus generalista declarado como vía | `cassandra/docs/ensemble_table.md` §2 y §5 |
| Activación de `isolation: netns` por despliegue | Heredado de v1.1.0: hosts sin user namespaces fallarían cerrado; activar en WSL2/Linux con userns | `atlas/config.yaml` (`safety.sandbox.isolation`) |
