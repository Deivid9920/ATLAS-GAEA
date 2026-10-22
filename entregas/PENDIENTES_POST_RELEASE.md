# Pendientes post-release — NO aplicar antes del tag v1.0

Estado: **DOCUMENTADO, NO EJECUTADO**. Las anclas quedan congeladas en el momento del
release. Cualquier cambio posterior a tests requiere: autorización explícita del operador,
registro en `atlas/docs/ANCHOR_CHANGES.md`, re-corrida completa de la suite (182/182) y
`audit-verify` ok. Este documento pre-registra la enmienda ANTES de aplicarla, con el mismo
espíritu de preregistro del resto del ecosistema.

## Enmienda de higiene de test (candidato #10 a ANCHOR_CHANGES.md)

Fila lista para añadir a `atlas/docs/ANCHOR_CHANGES.md` cuando el operador autorice,
SOLO después del tag v1.0:

| # | File | Change | Justification | Authorization |
|---|------|--------|---------------|---------------|
| 10 | `tests/test_probe_and_cache.py` | `test_probe_recalibration_job_logs`: usar `tmp_path` como `repo_root` del `ProbeVerifier` (hoy recibe `tmp_path` y lo ignora; escribe al log REAL `logs/probe_recalibration.jsonl`) | Higiene de repo público: cada `make test` anexa un registro al log real y deja `git status` sucio tras la suite. El estado runtime no es evidencia versionable; el log real se alimenta por `recalibrate()` en operación, no por la suite de tests. La operación append-only de `recalibrate()` no cambia. | PENDIENTE de autorización del operador. Aplicar post-v1.0 con registro en ANCHOR_CHANGES.md y re-corrida completa (182/182 + audit-verify + recomputo de huellas). |

Efecto esperado tras aplicar: `make test` ya no muta `logs/probe_recalibration.jsonl`;
`git status` queda limpio después de la suite; el comportamiento de `recalibrate()`
en operación (append-only) permanece intacto.

Contexto completo de la causa raíz: sección "Salvedad de la verificación externa
independiente" en `ATLAS_fase7_cierre_anexo.md` (este directorio).

## Otros pendientes que NO forman parte de esta enmienda

- `cloud_reference`: sigue null por no-go vinculante. Activarlo exige decisión explícita
  del operador por fuera de esta enmienda (no es un cambio de tests sino de alcance).
- `atlas_int8`: requiere hephaestus con eje int8 habilitado (cambio de build del generador
  → nueva huella de binario → nuevo registro S-01). Fuera del alcance del release v1.0.
- Probe CASSANDRA en vivo: requiere cablear el runtime CASSANDRA y recalibración con
  prereg nuevo antes de datos.
