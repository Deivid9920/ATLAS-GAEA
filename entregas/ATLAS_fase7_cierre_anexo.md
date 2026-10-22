# Anexo de cierre — FASE 7 de ATLAS (resultado de ejecución)

Fecha: 2026-10-21. Contrato de cierre de 7 puntos, fail-loud, sin cambio de alcance.
Complementa `docs/ANEXO_CIERRE_fase7_atlas.md` (incluido en el paquete) con el resultado mecánico del gate.

## Identidad del paquete final

| Elemento | Valor |
|---|---|
| Paquete | `download/ATLAS_entrega_Completa.zip` (101,972 bytes; 103 archivos) |
| SHA256 del zip | `f17b98dcba859de709291d0b1a70e5e4c770a3e72735a4b37625744d46b8159e` |
| SHA256SUMS (dentro del zip, rutas del árbol) | `SHA256SUMS.txt` — 4 entradas |
| Commit FASE 7 | `df4eb6f` (repo `atlas/`; árbol entregado byte-idéntico salvo `.git`) |
| Tag | `v1.0` (annotated, sobre `df4eb6f`) |
| Insumo S-01 auditado | zip anterior `59f2a42a…81e11e` — verificado ANTES de abrir |
| gaea_v | NO regenerado — congelado en `a52277d` (F-7 verde), `gaea_v_entrega.zip` intacto |

## Entradas del SHA256SUMS.txt (verificación del árbol entregado)

```
886254a77b4df8d6233be170dfe5c9fe73f8b9e4a347022cd88e72e5d7eef1a5  README.md
88b19e9ec5ff61928b824695e06695b5a865694c2f5314e9b29f62799f1d7eb1  config.yaml
dccf89e0185340a9e0028ee2fdcd61e43c13eeacaf2f0e5d666036a29fcfb85d  logs/audit.jsonl
c701611f6a9149d302f1b6838387f6dbbada50af3668c6f8bee9060622d19832  artifacts/selfplay/measure_50tasks.json
```

En extracción fresca: `sha256sum -c SHA256SUMS.txt` → **4/4 OK** (defecto 3/4 declarado, corregido).

## Gate de entrega: arnés Anexo E — 8/8 PASS

Arnés: `scripts/anexo_e_atlas.py` (fuera del árbol auditado). Estructura idéntica al arnés
Anexo E de gaea_v (`scripts/anexo_e_audit.py`), re-apuntada al paquete ATLAS; adaptaciones
declaradas en su docstring (sumas dentro del paquete, 182/182 exacto, hermanos enlazados
junto a la extracción, citaciones locales + del hermano). Ejecución sobre extracción
fresca del zip final con venv nueva:

```
[PASS] 1 sha256sum -c (arbol entregado): 4/4 OK, files_in_zip=103
[PASS] 2 pytest en extraido (venv nueva): 182/182 passed
[PASS] 3 audit-verify: entries=9 ok=True
[PASS] 4 anclas + huellas congeladas + preregs: anchors=True heph=True nano=True holdout=True preregs=True
[PASS] 5 manifiestos y numeros: run_ids=6 missing=[] neutral=[] nums=True
[PASS] 6 FORBIDDEN_MARKERS: anchor=True hits=0
[PASS] 7 tamper detectado: ok=False first_bad_seq=0
[PASS] 8 citaciones README: local=4 remote=8 missing=0
TOTAL: 8/8 PASS
ZIP_SHA256: f17b98dcba859de709291d0b1a70e5e4c770a3e72735a4b37625744d46b8159e
```

Detalle de cada verificación:

1. **Sumas del árbol entregado**: 4/4 OK en la extracción (rutas relativas del paquete; sin entradas inverificables).
2. **Suite ATLAS 182/182**: `make setup` (venv nueva) + `make test`, contra el binario real del hermano (`../hephaestus` enlazado junto a la extracción).
3. **`make audit-verify`**: cadena íntegra, 9 entradas, `ok=true`, `first_bad_seq=null`.
4. **Anclas + identidades congeladas + preregs**: tests de anclas del paquete en verde; huellas del hermano recomputadas — binario heph `23981267…d3eec`, pesos nano_fp32 `499e8c53…90190`, holdout `62d8992a3add…` y champion `499e8c53…` en `champion_tag.json`; preregs RFT v2 `cf38d994…` y bench 3col `421d8e88…` recomputados con el método congelado `prereg_hash` (import de solo lectura desde gaea_v).
5. **Manifiestos y números**: 6 run_ids citados en el README existen en `gaea_v/artifacts/runs/` con manifest; 0 faltantes; ningún manifest con `probe_status: neutral`; todos los números centrales del README == manifiestos (F4 nano 0.0/ATLAS 1.0, 200 vs 400 nodos; bench nano 0.0 acc / 22.8582 CPU-s / 0 nodos; atlas 0.5 acc / 245.6482 CPU-s / 800 nodos; H3 0.50 vs 0.25; H1 not claimed delta 0.0; H2/H3/HB1 claimed; RFT 0/800 con causa `empty_accepted_set`; linaje `expand=false` causa G3; int8 `not_measurable`; `cloud_reference: null` en config del paquete).
6. **FORBIDDEN_MARKERS**: test ancla `test_no_ai_markers` + barrido heurístico (misma lista que el arnés gaea_v, mismo alcance de ancla) sobre código/docs/raíz del paquete: 0 incidencias.
7. **Tampering**: copia del árbol con 1 byte alterado en `logs/audit.jsonl` → `audit_verify` lo detecta (`ok=false`, `first_bad_seq=0`).
8. **Citaciones README**: las 12 referencias (4 locales del paquete + 8 del hermano gaea_v) resuelven a archivos existentes; 0 faltantes.

## Contrato punto por punto

1. **S-01 identidad del insumo**: SHA256 `59f2a42a…81e11e` verificado antes de abrir. PASS.
2. **Entorno**: `ATLAS_heph_artifacts.zip` no está en disco; el hermano ya restaurado — huellas congeladas verificadas DIRECTAMENTE sobre `../hephaestus` (requisito funcional cumplido y anotado). Tests de bridge corridos contra el binario real.
3. **Alcance estricto**: solo ATLAS cambió (README + anexo + SHA256SUMS.txt); `git diff --stat` del commit lo confirma — anclas intactas; gaea_v sin tocar; ningún umbral congelado alterado; sin prereg nuevo (cambio documental/de empaquetado, sin datos).
4. **README**: tabla "Measured metrics" rellenada (16 filas), run_id/artefacto por celda, PENDIENTES con causa (cloud_reference null por no-go; atlas_int8 not_measurable con causa mecánica `fase6_h4_int8.json`). Ninguna cifra imputada: todas contrastadas por el arnés (paso 5).
5. **Empaquetado**: barrido genérico `.gitkeep` (0 vacíos tras el barrido); sin `.git/`/`.venv`/caches (guard 0); SHA256SUMS regeneradas con rutas del árbol → 4/4 OK en extracción fresca.
6. **Gate de entrega**: arnés Anexo E 8/8 PASS (arriba), suite 182/182, `audit-verify` ok; commit propio `df4eb6f` + tag `v1.0`.
7. **Entrega**: zip final + SHA256SUMS (`download/SHA256SUMS_ATLAS_entrega.txt`, mismo contenido que el interno) + este anexo. `gaea_v_entrega.zip` intacto.

## Defectos declarados → corregidos

| Defecto declarado en el contrato | Estado |
|---|---|
| Tabla "Measured metrics" en "pending first run" | CORREGIDO: 16 filas con fuente por celda |
| SHA256SUMS 3/4 en extracción fresca (rutas antiguas + self-hash) | CORREGIDO: 4/4 OK (paso 1 del arnés) |
| `ATLAS_heph_artifacts.zip` ausente | MITIGADO: hermano ya en disco con huellas congeladas exactas (verificación directa registrada) |

## Salvedad de la verificación externa independiente (registro de cierre)

> Nota de versión: esta copia del anexo añade la salvedad siguiente, registrada por la
> verificación externa independiente del operador (2026-10-21). El original dentro del
> zip congelado (`ATLAS_entrega_Completa.zip`, sha256 `f17b98dc…8159e`) no se modifica;
> esta copia es la versión de referencia para el repositorio.

La comparación zip-vs-zip (entrega final `f17b98dc…` contra insumo auditado `59f2a42a…81e11e`)
muestra un cuarto archivo distinto además de los tres declarados arriba:
`logs/probe_recalibration.jsonl` pasa de 30 a 28 líneas. El árbol entregado pierde las 2
líneas `{"status": "unavailable", "reason": "CASSANDRA repo not found"}` que el insumo
arrastraba. Causa raíz verificada empíricamente: `recalibrate()` es append-only y el test
`test_probe_recalibration_job_logs` anexa un registro al log REAL del repo en cada corrida
de la suite (recibe `tmp_path` y no lo usa como `repo_root`). Las 2 líneas del insumo eran
apéndices runtime del working tree de una corrida anterior, no evidencia committed; el zip
final se empaquetó desde el árbol git limpio (commit `df4eb6f`), por lo que el log revierte
a su estado committed (28 líneas). Comprobación: una corrida de la suite sobre extracción
fresca añade exactamente 1 línea a ese archivo (reproducido por el auditor externo). No hay
pérdida de evidencia comprometida: `logs/audit.jsonl` (9 eventos) es byte-idéntico al
insumo. Se registra por honestidad radical y como insumo de la enmienda de higiene
propuesta en `PENDIENTES_POST_RELEASE.md` (test #10, post-release).
