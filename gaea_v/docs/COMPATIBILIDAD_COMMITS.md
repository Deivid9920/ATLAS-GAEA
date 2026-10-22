# Compatibilidad de commits — reconstrucción exacta de cada experimento

Regla de la casa: cada artefacto de medición lleva el identificador del
estado del mundo con el que se produjo. Este manifiesto reconcilia las
referencias a `atlas_git_head` que aparecen en los artefactos de GAEA-V
con la historia de ATLAS, de modo que cualquier experimento pueda
reconstruir la combinación exacta de componentes que lo generó.

## Cadena de heads de ATLAS (secuencia temporal legítima)

| Head | Qué fue | S-01 invariante |
|---|---|---|
| `ecb494b` | Congelación del champion nano (bridge 5/5, evento genesis); pilotos de varianza (`pilot_atlas`, `pilot_nano_solo`) | binario `23981267…` · pesos `499e8c53…` · holdout `127ef76be…` |
| `4427672` | Enmienda S-08 (plugin `policy` con hard-block, peso 0.0); zoo baseline re-leído; FASE 5 (H3/H4/RFT) y FASE 6 (bench 3 columnas) | ídem |
| `df4eb6f` | Cierre FASE 7 + entrega v1.0 (gate verde 8/8; enmienda S-08 aplicada desde `4427672`) | ídem |

Las tres referencias SON la misma línea histórica: `ecb494b` →
`4427672` → `df4eb6f`. Ninguna es una rama divergente ni una
contradicción: es la cadena de commits de ATLAS al tiempo de cada
medición.

## Dónde vive cada referencia

| Artefacto | `atlas_git_head` | Nota |
|---|---|---|
| `gaea_v/artifacts/champion_tag.json` | `ecb494b` | congelación del champion (FASE -1 / genesis) |
| `gaea_v/artifacts/runs/pilot-pilot_atlas-18f52267/manifest.json` | `ecb494b` | piloto de varianza |
| `gaea_v/artifacts/runs/pilot-pilot_nano_solo-18f52267/manifest.json` | `ecb494b` | piloto de varianza |
| `gaea_v/config.yaml` (`identities.atlas_git_head`) | `4427672` | identidad del hermano congelada tras S-08 |
| `gaea_v/artifacts/zoo_baseline.json` (`source_head`) | `4427672` | re-lectura del zoo tras la enmienda S-08 |
| `gaea_v/artifacts/runs/h3_*/manifest.json`, `h4_nano_fp32/manifest.json` | `4427672` | FASE 5 (prereg v2) |
| `gaea_v/artifacts/runs/bench_atlas/manifest.json`, `bench_nano_solo/manifest.json` | `4427672` | FASE 6, bench 3 columnas |
| `atlas/` (entrega v1.0, commit interno) | `df4eb6f` | cierre FASE 7; `SHA256SUMS_ATLAS_entrega.txt` |

## Qué reconstruye un experimento publicado

Cada manifiesto de run lleva además: `heph_binary_sha256`,
`weights_sha256`, `config_sha256`, `suite_digest`, `prereg_sha256`,
`seed` y `run_id`. La combinación `(atlas_git_head, binario, pesos,
config, prereg, seed)` reconstruye la corrida bit-a-bit en un entorno
CPU-only. Las identidades S-01 (binario, pesos, holdout) son
INVARIANTES a lo largo de toda la cadena: ningún head cambió el
sustrato congelado.

## Historial posterior al release v1.0

| Commit del monorepo | Contenido |
|---|---|
| `25bf247` (tag `v1.0`) | publicación v1.0: ATLAS F0-F7 (`df4eb6f`) + GAEA-V F-1..F-7 (`a52277d`) |
| `1f0e5d8` (v1.0.1) | restauración de evidencia `atlas/` excluida por `.gitignore` interno (logs, artifacts, memory) + modo ejecutable de `heph` |
| v1.0.2 | higiene lote 1: validación de pesos del verificador compuesto, honestidad del sandbox (`isolation_profile` / `no_network_requested`), guard fail-loud en `make rft`/`make lineage`, `p_resolution` en `paired_bootstrap`, este manifiesto (ver ANCHOR_CHANGES de cada componente) |

Los cambios post-release no tocan el sustrato S-01 ni regeneran
artefactos congelados.
