# Release v1.1.0 — Lote 2: sandbox real fail-closed + CLIs de harness

Fecha: 2026-10-23. Tag `v1.1.0` (anotado) sobre `main`, después de `3c622cb`
(v1.0.2). Primera versión MINOR post-release: funcionalidad nueva, cero cambios
en datos, artefactos congelados o identidades.

## Origen

Lote 2 del plan de 3 lotes autorizado tras la auditoría externa verificada.
Cumple los dos pendientes declarados públicamente desde v1.0.2 (README raíz):
aislamiento real del sandbox y CLIs `rft`/`lineage`, más el piping del perfil
a la cadena de auditoría.

## Estado tras el cambio

- **ATLAS**: suite **199/199 PASSED** (187 de v1.0.2 + 12 nuevos: 4 del sandbox
  real, 2 del piping de auditoría, 6 de los wrappers de harness).
- **GAEA-V**: suite **109/109 PASSED** (sin cambios — el harness no se tocó).
- `audit-verify` ATLAS {entries: 9, ok} y GAEA {entries: 53, ok}.
- Bridge-check 4/4 con huellas exactas de binario y pesos.

## Qué cambia (3 enmiendas, todas documentadas en `ANCHOR_CHANGES.md`)

1. **#14 — Sandbox con aislamiento REAL, fail-closed**
   Nuevo `safety.sandbox.isolation`: `"none"` (default) | `"netns"`.
   - `netns` + `no_network`: el hijo corre bajo `unshare --net` → sin red a
     nivel OS; el resultado reporta `no_network_enforced: true` y
     `isolation_profile: subprocess+rlimits+netns`.
   - **Fail-closed**: si el host no puede crear el namespace, el verificador
     levanta `IsolationUnavailableError` ANTES de lanzar el hijo — jamás corre
     con red "por si acaso". Requiere WSL2/Linux con user namespaces.
   - Default `none`: rlimits sin bloqueo de red, reportado sin maquillaje
     (`no_network_enforced: false`). La honestidad no es opcional: el campo
     siempre dice la realidad.
2. **#15 — Piping del aislamiento a la cadena de auditoría**
   Los eventos `verifier_decision` llevan
   `sandbox_isolation: {isolation_profile, no_network_requested,
   no_network_enforced}` cuando el verificador expone el dato; si no lo hay,
   el campo NO se inventa. Los eventos históricos congelados no cambian.
3. **#16 — CLIs `rft`/`lineage` reales (fin de los esqueletos)**
   `make rft STAGE=...` / `make lineage STAGE=...` invocan el harness que
   midió las FASES 5-6 (`gaea_v/scripts/run_fase5.py` / `lineage_measured.py`)
   con el preregistro obligatorio ANTES de datos, imprime su sha256 y propaga
   el exit code. Fail-loud con causa nombrada (exit 2) si falta el hermano
   gaea_v, el harness o el prereg. La identidad S-01 la aplica el propio
   harness (`AtlasHook.verify_identity`). Re-ejecutar una ronda produce
   artefactos NUEVOS — el wrapper lo avisa honestamente.

## Identidades congeladas S-01 — INTACTAS

| Identidad | sha256 (prefijo) |
|---|---|
| Binario `heph` | `23981267e759028d…` |
| Pesos champion `nano_fp32` | `499e8c5313f33522…` |
| Holdout | `127ef76be336d516…` (el archivo se llama por su propio sha256) |

## Assets

**Sin assets nuevos.** Los artefactos congelados siguen viviendo en el Release
v1.0 ("Hashes and Pre-existing Models") y NO se regeneran. "Un clone fresco
funciona" sigue siendo literalmente cierto en `main`.

## Pendientes declarados (Lote 3, por definir)

- Activación de `isolation: netns` en el despliegue del operador (WSL2) — la
  capacidad existe; el default de repo sigue siendo `none` a propósito.
- Re-ejecución de una ronda RFT/linaje con prereg NUEVO antes de datos.
- Probe CASSANDRA en vivo (requiere el runtime CASSANDRA cableado).
