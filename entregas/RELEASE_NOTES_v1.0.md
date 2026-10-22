# Release v1.0 — Cierre del ecosistema ATLAS + GAEA-VERIFICADOR

Fecha de congelación: 2026-10-21. Texto sugerido para la página del GitHub Release
(tag `v1.0` sobre el commit de FASE 7 de ATLAS, `df4eb6f`).

## Estado

- **ATLAS**: FASES 0-7 completas. Suite 182/182 PASSED. Cadena de auditoría íntegra
  (9 eventos, `first_bad_seq null`). Gate de entrega: arnés Anexo E, 8/8 PASS.
- **GAEA-VERIFICADOR** (`gaea_v`): FASES -1 a 7 con gates verdes, congelado en `a52277d`
  (no regenerado en este cierre). Suite 108/108 PASSED. Verificación externa 8/8,
  humo bit-idéntico (run `048e92241fa8`).
- **Identidades congeladas verificadas**: binario heph `23981267…`, pesos champion
  `499e8c53…`, holdout `127ef76be336…` (el archivo se llama por su propio sha256),
  documento maestro `ae409daf…`.

## Resultados reclamados (preregistro antes de datos, Holm, doble condición)

- H2 (ATLAS > nano): delta 0.5, IC [0.4, 0.6], p_holm 0.0 — RECLAMADA
- H3 (poda por verificador > aleatoria): delta 0.25, IC [0.17, 0.34], p_holm 0.0 — RECLAMADA
- HB1 (bench 3 columnas, ATLAS > nano_solo): delta 0.5, IC [0.4, 0.6], p_holm 0.0 — RECLAMADA

## Resultados honestos (lado que también importa)

- RFT ronda 1: 0/800 candidatos aceptados (causa `empty_accepted_set`); entrenamiento omitido con causa.
- H1 (auto-mejora neta): NO reclamada (delta 0.0).
- H4 / atlas_int8: NOT_MEASURABLE con causa mecánica registrada.
- Linaje G1-G4: expand=false, causa G3 pacing.
- cloud_reference: null por no-go vinculante de nube.

## Assets del Release

| Asset | sha256 (prefijo) |
|---|---|
| `ATLAS_entrega_Completa.zip` | `f17b98dcba859de709291d0b1a70e5e4c770a3e72735a4b37625744d46b8159e` |
| `gaea_v_entrega.zip` | `24fca1e8…` (añadir el zip original desde el disco del operador; NO regenerar) |
| `SHA256SUMS_ATLAS_entrega.txt` | igual al archivo interno del zip |
| `SHA256SUMS_GAEA_V.txt` | 4/4 OK contra el original |
| `ATLAS_fase7_cierre_anexo.md` | copia de referencia con salvedad de cierre |
| `ATLAS_GAEA_informe_entrega.pdf` | informe verificable de 12 páginas |

## Verificación mecánica (para el auditor)

1. `git lfs install` antes de clonar; verificar pesos: `sha256sum hephaestus/artifacts/nano_fp32.safetensors` → `499e8c53…`.
2. `cd atlas && make setup && make bridge-check && make test` → puente 5/5, suite 182/182.
3. `make audit-verify` → ok, `first_bad_seq null`.
4. `cd ../gaea_v && make setup && make test && make audit-verify` → 108/108, cadena ok.
5. Verificación completa estilo Anexo E (8 pasos): `entregas/ATLAS_fase7_cierre_anexo.md`.
