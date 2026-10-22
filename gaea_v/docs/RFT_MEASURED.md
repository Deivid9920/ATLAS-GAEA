# RFT_MEASURED.md — FASE 5 medida (cada número con run_id)

Preregistro: `prereg_20261020_rft_rondas_v2`
(hash `cf38d994811def7ff080a134283d501637512340fa23b0dcd8ff491b765303c7`,
encadenado antes de cualquier corrida inferencial; enmienda v1→v2
registrada en docs/ANCHOR_CHANGES.md con la rectificación de la
corrida muerta 7d021e2f8afa). Regla congelada: `p_holm<0.05 AND
ci_excludes_0; TOST inside epsilon 0.15`. Única lectura inferencial:
la final, sobre la familia completa, con Holm.

## Ronda 1 del loop RFT (a través del arnés gv)

| Etapa | Artefacto / run_id | Resultado |
|---|---|---|
| Candidatos | `artifacts/rft/round_1/candidates.jsonl` | 800 textos (50 tareas del corpus_rft × 16 temperaturas 0.50–1.25); contaminación 0 impactos |
| Filtro compuesto | `artifacts/rft/round_1/filter_rows.jsonl` | 0/800 aceptados (approve + tests) — el nano degenerado no produce ningún candidato aprovechable |
| Evaluación ronda | run `6370c75420b7` (condición rft_round_1, escalera 100, frontera única) | accuracy 0.0000 (t1/t2/t3 = 0.0/0.0/0.0) |
| Entrenamiento | `artifacts/rft/round_1/round_manifest.json` | skipped — causa: empty_accepted_set (0/800); sin pesos fabricados; semillas declaradas 101/202/303 |
| Diversidad de trazas | `artifacts/rft/round_1/diversity.json` | entropía clústeres MinHash: baseline 1.0 → ronda 1.0; caída 0.0 (gate NS de diversidad PASA; techo de medición documentado) |

Lectura honesta: la ronda 1 nace medida pero NO promueve. El
champion sigue siendo el congelado (weights_sha256 499e8c53...).

## Familia inferencial final (Holm sobre H1, H2, H3; H4/H5 por su contrato)

| Hipótesis | Delta | IC95 bootstrap | p | p_holm | Reclamada |
|---|---|---|---|---|---|
| H1 ronda_final > baseline | 0.0000 | [0.0000, 0.0000] | 1.00 | 1.00 | NO |
| H2 atlas > nano_solo re-baselined | 0.5000 | [0.4000, 0.6000] | <0.0001 | <0.0001 | **SÍ** |
| H3 poda_verificador > poda_aleatoria | 0.2500 | [0.1700, 0.3400] | <0.0001 | <0.0001 | **SÍ** |

Runs que alimentan cada contraste (declarados en el prereg):
- H1: run `6370c75420b7` (rft_round_1) vs run
  `pilot-pilot_nano_solo-18f52267`, emparejado por task_id (n=100).
- H2: run `pilot-pilot_atlas-18f52267` vs run
  `pilot-pilot_nano_solo-18f52267` (n=100).
- H3: run `h3_poda_verificador` (accuracy 0.5000, 400 nodos) vs run
  `h3_poda_aleatoria` (accuracy 0.2500, 400 nodos) — mismo
  presupuesto de nodos, escalera completa n=100, budget fast,
  max_iters 1.
- H4: NO EVALUABLE — causa encadenada (`h4_not_measurable`) ANTES
  del unblinding: heph genera solo en fp32 en este build (la
  cuantización int8 es in-memory en bench; qint8/weights.bin es
  artefacto de export, no entrada del cargador). Brazo fp32 medido y
  conservado: run `h4_nano_fp32` (accuracy 0.0000, n=100).
- H5: TOST sobre delta = diversidad_ronda − 0.80·diversidad_baseline
  con re-muestreo de trazas (2000, semilla 42): delta puntual 0.2000,
  IC90 [0.2000, 0.2000] vs epsilon 0.15 → inside=false; el punto
  sostiene el piso (floor_holds_point=true) y el gate NS de
  diversidad pasa (caída de entropía 0.0 ≤ 0.20). Limitación
  declarada: pairwise_diversity satura en 1.0 para conjuntos de
  trazas cortas distintas (techo de medición), lo que vuelve
  degenerado el contraste TOST en este corpus.

## Decisión de promoción de la ronda 1

`promotion_refused` (encadenado). Causas enumeradas:
1. H1 no supera la regla doble (delta 0.0000, IC incluye 0, p_holm
   1.00): la ronda no mejora al baseline.
2. Gate NS de ppl: sin entrenamiento no hay pesos nuevos; el holdout
   congelado no mueve ppl ≥ 1%.
3. Veto topológico V2 disponible pero ausente (probe
   desactivado/probe_desactivado): ronda sin veto Y sin promoción
   (sensor ausente no es sensor conforme).

## Hallazgos medidos de la ronda

- El canal ATLAS (retrieval + MCTS + verificación) supera al
  nano-solo con delta 0.5000 [0.4000, 0.6000] sobre 100 tareas —
  primera afirmación inferencial del ecosistema, nacida con
  preregistro y Holm.
- La poda por verificador supera a la poda aleatoria con delta
  0.2500 [0.1700, 0.3400] a IGUAL presupuesto de nodos (400 vs 400):
  la calidad del verificador, no el presupuesto, produce la ganancia.
- El loop RFT con el champion degenerado no produce material de
  entrenamiento (0/800); el cuello es el generador, no el filtro.
