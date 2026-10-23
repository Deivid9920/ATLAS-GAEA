# Release v1.0.2 — Lote 1 de higiene (auditoría externa verificada)

Fecha: 2026-10-23. Tag `v1.0.2` (anotado) sobre el commit `3c622cb`, en `main`
después de `1f0e5d8` (v1.0.1). Historia lineal: `25bf247 (v1.0) → 1f0e5d8 (v1.0.1) → 3c622cb (v1.0.2)`.

## Origen

Auditoría externa independiente verificada claim por claim (12/12 verídicos, con
matices auto-declarados por el propio sistema de honestidad radical). Plan de
mejora en 3 lotes autorizado por el operador. **Este release es el Lote 1:
higiene de interfaz y honestidad — sin tocar datos, artefactos ni identidades.**

## Estado tras el cambio

- **ATLAS**: suite **187/187 PASSED** (182 previos + 5 nuevos: 4 de frontera de
  pesos, 1 de `isolation_profile`; y el test de probe corregido por enmienda #13).
- **GAEA-V**: suite **109/109 PASSED** (108 previos + 1 nuevo de `p_resolution`).
- Cadena de auditoría íntegra: `audit-verify` ATLAS {entries: 9, ok} y GAEA
  {entries: 53, ok}, `first_bad_seq: null` en ambas.
- Bridge-check 4/4 PASS resolviendo binario y pesos con huellas exactas.
- `make rft` / `make lineage`: guard fail-loud con mensaje PENDIENTE declarado,
  exit code 2 (antes: traceback `NotImplementedError` opaco).
- **La suite ya no deja `git status` sucio** (enmienda pre-registrada aplicada).

## Qué cambia (8 ítems, todos documentados en `ANCHOR_CHANGES.md`)

1. **`composite.py`** (ancla): `register()` valida pesos — finitos y `>= 0`
   (0.0 sigue legal: voto de policy S-08); `evaluate()` falla con `ValueError`
   nombrado si la suma de pesos es 0 (antes: `ZeroDivisionError` opaco o
   corrupción silenciosa con pesos negativos/NaN). 4 tests de frontera nuevos.
2. **`programmatic.py`**: `no_network_enforced` → `no_network_requested` (refleja
   la PETICIÓN de config, no una propiedad verificada) + campo
   `isolation_profile: "subprocess+rlimits"` + guard fail-loud en Windows con
   causa accionable + docstring corregida (el endurecimiento real del sandbox es
   el Lote 2, declarado como pendiente).
3. **`Makefile`**: targets `rft`/`lineage` ya no invocan esqueletos que crashean;
   imprimen el PENDIENTE declarado con puntero al harness que midió la fase
   (`gaea_v/scripts/run_fase5.py`, `lineage_measured.py`) y salen con código 2.
4. **`stats_core.py` (GAEA)**: `paired_bootstrap` añade `p_resolution = 1/resamples`
   — un `p=0.0` es el suelo de resolución de Monte Carlo, no probabilidad literal
   cero. Valores previos bit-idénticos; ancla de esquema actualizada solo para
   añadir el campo (enmienda registrada en `gaea_v/docs/ANCHOR_CHANGES.md`).
5. **Enmienda pre-registrada aplicada (fila #13)**: `test_probe_recalibration_job_logs`
   usa `tmp_path` como `repo_root` — la suite ya no anexa registros al log real
   `logs/probe_recalibration.jsonl`. Pre-registrada ANTES de datos en
   `entregas/PENDIENTES_POST_RELEASE.md`, aplicada con autorización del operador.
6. **`gaea_v/docs/COMPATIBILIDAD_COMMITS.md` (nuevo)**: reconcilia la cadena
   `ecb494b → 4427672 → df4eb6f` con el artefacto donde vive cada referencia.
7. **`ANCHOR_CHANGES.md` (ambos componentes)**: enmiendas #10, #11, #12, #13
   (ATLAS) y enmienda de esquema 2026-10-22 (GAEA), con autorización del operador.
8. **README raíz**: conteos de suite actualizados (187/109), 2 pendientes nuevos
   declarados (CLIs stub y sandbox real), enlace al manifiesto de compatibilidad.

## Identidades congeladas S-01 — INTACTAS (verificadas antes y después del cambio)

| Identidad | sha256 (prefijo) |
|---|---|
| Binario `heph` | `23981267e759028d…` |
| Pesos champion `nano_fp32` | `499e8c5313f33522…` |
| Holdout | `127ef76be336d516…` (el archivo se llama por su propio sha256) |

## Assets

**Sin assets nuevos, deliberadamente.** Los artefactos congelados (zips de
entrega, modelos, SHA256SUMS) viven en el Release **v1.0** — "Hashes and
Pre-existing Models" — y NO se regeneran: este release documenta cambios de
código solamente. La promesa "un clone fresco funciona" sigue siendo literalmente
cierta en `main` (verificada en clones prístinos: parche aplica limpio, suites
verdes, árbol limpio tras la suite).

## Pendientes declarados (Lote 2, autorización pendiente)

- Sandbox real: `no_network` verificado de verdad (WSL2/container fail-closed),
  no solo solicitado por config.
- Port de los CLIs `rft` / `lineage` al harness real de gaea_v.
- Piping del perfil de aislamiento al evento de auditoría.
