# PROTOCOLO_ESTADISTICO.md — la biblioteca única y su validación

## Regla de unicidad (FASE 1)

`gv/stats/stats_core.py` es la única implementación estadística del
ecosistema: ATLAS y GAEA importan de aquí. Ninguna función se copia
de CASSANDRA con ediciones; la disciplina (bootstrap pareado, Holm,
ECE) se trasladó como funciones nuevas con anclas propias. Funciones
congeladas por ancla: `wilson_ci`, `paired_bootstrap`, `holm`,
`tost_equivalence`, `ece`, `auc_ci`, `power_epsilon`. Purezas: sin
I/O, semilla por parámetro.

## Contratos numéricos (sección 4 del documento maestro)

- Bootstrap pareado por tarea: 10.000 remuestreos, IC percentil 95%,
  semilla 42.
- Regla de afirmación doble: se afirma un efecto solo si
  p_holm < 0.05 Y el IC95% excluye 0; sin ambas condiciones el
  desenlace es "no concluyente" y se reporta como tal.
- TOST: equivalencia dentro de épsilon con IC90% del delta; el borde
  exacto NO cuenta como dentro (ancla test_tost, caso límite
  congelado).
- épsilon derivado de potencia por simulación con la semilla
  congelada ANTES de cualquier comparación real (FASE 2).
- Holm paso-descendente sobre la familia pre-registrada cerrada.

## Validación contra verdad sintética (DoD de FASE 1)

Diseño: pares de 100 tareas binarias con tasa base 0.35 para la
condición B y efecto d añadido a la condición A; 5 simulaciones por
efecto con semillas fijas; regla doble aplicada con Holm sobre
p_two_sided del bootstrap pareado (10.000 remuestreos).

| Efecto d | Afirmaciones (5 sims) | Tasa |
|---|---|---|
| 0.00 | 0/5 (cero falsos positivos) | 0.00 |
| 0.05 | 4/5 | 0.80 |
| 0.20 | 5/5 | 1.00 |
| 0.50 | 5/5 | 1.00 |

Lectura honesta: con n=100 y varianza de Bernoulli, d=0.05 está en el
borde de la potencia del diseño (80% en este lote); el protocolo no
lo infla: lo reporta como lo que es. Los efectos d >= 0.20 se
recuperan de forma consistente y d=0 no produce ninguna afirmación
falsa en ninguna simulación.

TOST con d=0: épsilon derivado de potencia con var 0.25 es 0.15; el
IC90% del delta cae dentro y declara equivalencia, como debe.

Familia cerrada H(d=0, 0.05, 0.20, 0.50) con Holm:
p_holm = [1.0, 0.0642, 0.0024, 0.0]; rechazados: [F, F, T, T] — la
corrección conserva el control del error de familia y solo afirma
donde la evidencia lo sostiene.

## Valores congelados de las anclas (resumen)

- `wilson_ci(7,10)` = (0.39677321997956516, 0.892210712513788)
- `paired_bootstrap` sobre el par fijo (semilla 42): delta 0.4,
  IC95 [0.1, 0.7], p 0.021
- `holm([0.01,0.04,0.03,0.005])` = [0.03, 0.06, 0.06, 0.02]
- `power_epsilon(100, 0.25, 0.80, 42, 4000)` = 0.15 (evento TOST:
  |media| + hw < eps, validado contra la forma cerrada
  z80*se + z90*se)
