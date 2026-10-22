# METRICS_baseline.md — reproducción del baseline en ESTE entorno

Fecha de reproducción: 2026-10-19/20 (sandbox actual, sexta
restauración del ecosistema). Los cuatro insumos zip originales de
ATLAS no están presentes en este entorno; la identidad se verificó
mecánicamente contra las huellas congeladas, que son el contrato real:
cualquier byte distinto en binario, pesos, holdout o HEAD habría
detenido TODO (S-01).

## Huellas verificadas (mecánicas, este entorno)

| Ancla | Valor congelado | Verificación |
|---|---|---|
| Prompt maestro | `ae409daf4898ef10f7cf1f1f9017cfb09dc54fb8394238d0cd70b1b71873f6ca` | sha256 recalculado: OK |
| Binario heph | `23981267e759028d71a60d4bf644013c0d09da740c6385435e25e1a5606d3eec` | sha256 recalculado: OK |
| Champion nano fp32 | `499e8c5313f33522ba6b300013a177f60dd1fc9001ef2fd67c873aaa34e90190` | sha256 recalculado: OK |
| Holdout archivo | `127ef76be336d516bac911bffc68689022361947260a6097ae8df0dac411bbc0` | sha256 recalculado: OK |
| Holdout digest | `62d8992a3add265c68990949c7a4100ad412cd4c0b3f4d6f22153280d565d54e` | reproducido con `compute_holdout_digest` de prometheus-ns: OK |
| ATLAS git HEAD | `ecb494b` | git rev-parse: OK |
| Zips de entrega (4) | SHA256SUMS_ATLAS.txt | PENDIENTE: no presentes en este entorno; identidad cubierta por las huellas de arriba |

## Baseline reproducido

| Métrica | Valor | Fuente |
|---|---|---|
| Tests de ATLAS | 165/165 PASSED (22.5 s) | `pytest` en atlas/ (este entorno) |
| Cadena de auditoría ATLAS | ok, 9 entradas | `scripts/audit_verify.py` de ATLAS |
| Bridge-check | 5/5 (binario+pesos+canario+humo) | `make bridge-check` de ATLAS |
| Generación humo | `IGIGIGIGIGIGIGIG` (degenerada, esperada) | el nano es humo honesto; el delta del sistema se mide con búsqueda+verificación |
| Champion tag | congelado en `artifacts/champion_tag.json` | ppl holdout 3028.7 fp32; arch 6L/6H/d384/dff1024/vocab8000/seq256; n_kv_head = n_head = 6 (sin compresión GQA efectiva, congelado TAL CUAL) |

Cada evento anterior está encadenado en `logs/audit.jsonl`
(genesis → config_sha256 → champion_tag_frozen → bridge_check →
fase_minus1_baseline). `make audit-verify` verifica la cadena.
