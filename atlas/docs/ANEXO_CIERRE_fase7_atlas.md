# Anexo de cierre - FASE 7 de ATLAS

Fecha: 2026-10-21. Contrato de cierre ejecutado en 7 puntos, fail-loud, sin cambio de alcance.
Este anexo documenta cada verificación mecánica del cierre. Ninguna cifra es imputada.

## 1. Identidad del insumo (S-01)

- Insumo: `ATLAS_entrega_Completa.zip`.
- SHA256 esperado: `59f2a42ab0a7438d9bc2d756387a513d55881626cff3e73742bc1f9e6e81e11e`.
- SHA256 medido antes de abrir: idéntico. Verificación PASS; el paquete quedó autorizado a extraerse.

## 2. Entorno: hermano HEPHAESTUS

- `ATLAS_heph_artifacts.zip` no está presente en el disco de auditoría; el hermano
  `../hephaestus` ya está restaurado en disco. En lugar de re-extraer, se verificaron
  las huellas congeladas DIRECTAMENTE sobre el hermano (requisito funcional del punto 2):
  - binario `hephaestus/build/heph`: `23981267e759028d71a60d4bf644013c0d09da740c6385435e25e1a5606d3eec` PASS
  - pesos `hephaestus/artifacts/nano_fp32.safetensors`: `499e8c5313f33522ba6b300013a177f60dd1fc9001ef2fd67c873aaa34e90190` PASS
- Con el hermano en su lugar y las huellas conformes, los 7 tests de bridge corren contra el binario real.

## 3. Alcance estricto

- `gaea_v` permanece CONGELADO en `a52277d` (F-7 verde): usado como arnés de medición, sin modificaciones.
- Cambios en ATLAS en este cierre: `README.md` (tabla Measured metrics), `docs/ANEXO_CIERRE_fase7_atlas.md` (este anexo), `SHA256SUMS.txt` (identidad del paquete).
- Ninguna ancla tocada (`config.yaml`, `atlas_ns/audit/chain.py`, suites de tests, `Makefile`):
  verificado con `git diff --stat` antes del commit; sin prereg requerido porque no hay datos nuevos
  ni umbrales alterados (la edición es documental y de empaquetado).

## 4. README: tabla "Measured metrics"

- Defecto corregido: la tabla estaba "pending first run".
- Rellenada con lo YA medido, citando run_id/artefacto por celda:
  - FASE 4: `artifacts/selfplay/measure_50tasks.json` (nano 0.00 vs ATLAS 1.00; poda 200 vs 400 nodos).
  - FASE 5-F6 vía harness gaea_v (hermano congelado, read-only): bench 3 columnas (nano 0.0 acc /
    22.8582 CPU-s / 0 nodos; atlas 0.5 acc / 245.6482 CPU-s / 800 nodos), HB1 delta 0.5 IC [0.4, 0.6]
    p_holm 0.0, H2 y H3 CLAIMED, H1 delta 0.0 NOT claimed, RFT 0/800 con causa empty_accepted_set,
    H4/atlas_int8 NOT_MEASURABLE con causa mecánica (`fase6_h4_int8.json`), linaje expand=false con
    causa G3 pacing.
- Lo no medido declarado PENDIENTE con causa: cloud_reference null (no-go, requiere aprobación
  explícita del operador), atlas_int8 no medible (causa mecánica registrada).

## 5. Empaquetado (defecto 3/4 corregido)

- Barrido genérico `.gitkeep` en todo directorio vacío (4 presentes, 0 vacíos sin marcador).
- Exclusiones: `.git/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.pyc`.
- Defecto declarado: las SHA256SUMS previas usaban rutas antiguas (`atlas/...`, inexistentes dentro
  del árbol del zip) y una entrada inverificable (el hash del propio zip dentro del zip). Corregido:
  `SHA256SUMS.txt` regenerado con las rutas del árbol entregado (4 entradas). En extracción fresca,
  `sha256sum -c SHA256SUMS.txt` debe dar 100% OK (verificado por el arnés, paso 1).
- El hash del zip final se publica junto al paquete (SHA256SUMS_ATLAS_entrega.txt y anexo de entrega),
  no dentro de él.

## 6. Gate de entrega (arnés Anexo E, 8 pasos)

- Arnés: reutilización del procedimiento Anexo E del auditor (8 pasos mecánicos, fail-loud),
  fuera del árbol auditado (`scripts/anexo_e_atlas.py`), re-apuntado al paquete ATLAS.
- Sobre extracción fresca del zip final con venv nueva:
  1. `sha256sum -c SHA256SUMS.txt` -> 4/4 OK.
  2. `make test` sobre extracción con venv nueva -> 182/182 PASSED.
  3. `make audit-verify` -> ok=true, first_bad_seq=null.
  4. Recomputación de hashes de anclas y artefactos citados.
  5. Manifiestos: run_ids citados existen; números centrales = manifiestos; probe nunca "neutral".
  6. FORBIDDEN_MARKERS: test ancla `test_no_ai_markers` + barrido heurístico -> 0 incidencias.
  7. Tampering de 1 byte en copia del log -> detectado (ok=false, first_bad_seq no nulo).
  8. Citaciones del README: todas las rutas referenciadas existen (locales y del hermano gaea_v).
- Resultado del arnés: documentado en la sección de ejecución (8/8 PASS exigido para cerrar).

## 7. Commit y tag

- Commit propio de FASE 7 en el repo `atlas/` (README + anexo + SHA256SUMS.txt) y tag `v1.0`.
- Identidad del zip final publicada en el mensaje de entrega y en `download/SHA256SUMS_ATLAS_entrega.txt`.
- `gaea_v_entrega.zip` NO se regenera (intacto, congelado en a52277d).
