# ANCHOR_CHANGES.md — enmiendas a anclas y contratos

Sin enmiendas registradas. Las 14 anclas se congelaron en FASE 0 y
ninguna fue editada después de la congelación. Cualquier enmienda
futura se registra AQUÍ ANTES de ver datos afectados, con
justificación, autorización del operador y re-hash de config
(enmienda B1); un umbral cambiado después de ver datos mata la
afirmación asociada.

## 2026-10-20 — ancla `identities.atlas_git_head`: ecb494b → 4427672

Naturaleza: actualización de identidad de hermano, no de umbral
inferencial. Causa: el zoo baseline (FASE 3, S-08) midió catch
malicious 0.00 con tres APPROVE sobre ZOO-401/402/403; el prompt
maestro (FASE 3.e) ordena corregir el verificador ANTES de FASE 5 y
la corrección debe pasar por los gates de ATLAS, nunca por editar el
zoo. Fix: plugin `policy` en atlas_ns (commit 4427672 de atlas), voto
hard-block con peso 0.0 (aritmética ponderada intacta sobre
candidatos limpios); suite de ATLAS 182/182. La re-lectura del zoo es
parte del diseño de la regla de regresión congelada (zoo re-corre
contra cada config del verificador); no muere ninguna afirmación
inferencial porque el zoo no es una comparación de hipótesis.
Autorización: GO del operador sobre el plan maestro. Re-hash de
config encadenado en logs/audit.jsonl junto al evento de enmienda.

## 2026-10-20 — enmienda de prereg: rft_rondas v1 → v2 (sin datos)

Naturaleza: enmienda de prereg (S-20), no de umbral. La v1 declaraba
subconjuntos de 30 tareas T1 para H3/H4; el esquema del manifiesto
(Anexo A, congelado) exige n_tasks == 100 por run. Rectificación honesta: la PRIMERA
corrida v1 (h3_poda_verificador, run 7d021e2f8afa, 30 tareas) SÍ se
había ejecutado antes de la enmienda — falló la validación estricta
del manifiesto y su evento run_completed nunca llegó a encadenarse;
sus filas no fueron leídas inferencialmente. La corrida queda
INVALIDADA en la cadena (run_invalidated) y conservada en disco por
transparencia. La enmienda v2 se registró antes de que existiera
CUALQUIER dato H3/H4 válido. v2 declara la escalera completa para H3/H4 con
presupuestos idénticos por par. Nuevo hash encadenado
(cf38d994811def7f...); Holm corre sobre la familia v2.

## 2026-10-20 — H4 declarada no evaluable (antes del unblinding)

El build actual de heph genera solo en fp32: la cuantización int8 es
in-memory dentro del comando bench y `qint8/weights.bin` es un
artefacto de exportación, no una entrada del cargador (medido: error
"safetensors header exceeds file size"). El verificador tampoco tiene
eje int8/fp32 (el puente solo tokeniza). El brazo fp32 de H4 quedó
medido (run h4_nano_fp32, accuracy 0.0) y se conserva; la hipótesis
H4 se declara NO EVALUABLE con causa encadenada ANTES de la
inferencia final, y Holm corre sobre H1, H2, H3, H5. Sin lectura
inferencial previa al evento h4_not_measurable.

## 2026-10-21 — Reserva de campos GAEA-L en el manifiesto de eficiencia (FASE 6.d)

Naturaleza: enmienda de esquema (no de umbral), registrada ANTES de la
primera corrida de FASE 6. El prompt maestro (FASE 6.d) ordena reservar
en el manifiesto los campos de GAEA-L: substrate_id,
matching_params, matching_training_flops (doble eje; ambos se
reportan siempre; el matching solo-por-parámetros sesga a favor del
SSM). El esquema gv.manifest/1 es cerrado (campos desconocidos =
rechazo), así que la reserva se materializa ampliando el conjunto
cerrado de campos: los tres pasan a ser obligatorios en todo
manifiesto nuevo, con valor null cuando la condición no es un sustrato
GAEA, y los tres juntos cuando lo es (params y FLOPs de matching
nunca por separado). Los manifiestos ya publicados de las FASES 0-5
se conservan tal cual: son evidencia congelada y no se re-validan
contra el esquema ampliado. config.yaml no cambia (ningún umbral se
mueve); la enmienda queda anclada por tests del validador.
Autorización del operador: instrucción "Continua con la FASE 6".
