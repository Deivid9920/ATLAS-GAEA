# ANEXO_E_verificacion_externa.md — auto-verificación del paquete

FASE 7.d ordena: "Prueba el checklist del Anexo E contigo mismo".
Este doc registra la ejecución mecánica de los 8 pasos del auditor
externo y del checklist del agente contra el paquete entregado
(gaea_v_entrega.zip + SHA256SUMS_GAEA_V.txt). El arnés de auditoría
vive FUERA del árbol auditado (no es parte del repo ni del zip), y
audita una EXTRACCIÓN FRESCA del zip, nunca el árbol de trabajo.

## Los 8 pasos del auditor

Resultados del snapshot auditado (contenido idéntico al paquete
entregado salvo este documento, añadido después por necesidad de
orden; el paquete final fue re-auditado con el mismo arnés y las 8
líneas mantienen su resultado):

1. sha256sum -c SHA256SUMS_GAEA_V.txt -> 4/4 OK (zip, champion_tag,
   METRICS_baseline, suite_manifest).
2. extraer; python -m pytest en clon fresco (venv nueva, requirements
   instalados) -> 108 passed. La suite propia de gaea_v es 108; los
   165 originales de ATLAS (182/182 tras la corrección S-08) se
   reproducen desde el paquete ATLAS, no desde este zip: el puente es
   de solo lectura y los hermanos no viajan dentro del paquete.
3. make audit-verify -> ok=true, first_bad_seq null (52 eventos al
   momento del snapshot; la cadena del paquete final añade el evento
   de cierre de FASE 7).
4. recomputar config_sha256, suite_digest, prereg hashes -> match:
   config e37117b9... (canon yaml->json), suite_digest e775280a...
   (reconstrucción de la escalera desde profiles), prereg RFT v2
   cf38d994... y prereg bench 421d8e88... con el método congelado
   prereg_hash (sha256 canónico SIN created_utc, gv/stats/prereg.py).
5. abrir manifiestos: los 6 run_id citados en README existen con su
   manifest.json; probe_status nunca "neutral" en ningún run; los
   números núcleo cuadran contra manifiesto (nano 0.0 acc / 22.8582
   CPU-s; atlas 0.5 acc / 245.6482 CPU-s / 800 nodos; zoo catch 1.0
   fpr 0.0; RFT 800/0; HB1 delta 0.5 IC [0.4,0.6] reclamada).
6. buscar marcadores IA -> 0: ancla test_forbidden_markers verde en
   la extracción + barrido heurístico (frases Anexo D, emojis) sobre
   el MISMO alcance del ancla (gv, scripts, docs, profiles, archivos
   raíz). Los datos medidos congelados (artifacts/, logs/) quedan
   fuera del alcance POR DISEÑO DEL ANCLA: sus bytes están
   encadenados y editarlos para complacer un escáner sería tampering
   (S-16). Un U+FFFD en artifacts/rft/round_1/candidates.jsonl es
   ruido de texto generado medido, evidencia intacta.
7. S-01..S-20 spot: 1 byte alterado en el evento genesis de una COPIA
   de la cadena -> verify() falla con ok=false y first_bad_seq=0. La
   copia se alteró en el directorio temporal del arnés; el repo y el
   paquete quedan intactos.
8. ningún número de RFT/bench sin manifiesto: las 12 citaciones de
   artifacts/docs/logs en README resuelven a archivos existentes; el
   fallo inicial de este paso fue el propio doc de evidencia citado
   antes de existir (orden de escritura, corregido al añadirlo).

TOTAL snapshot: 7/8 PASS (el paso 8 falló solo por la ausencia de
este doc); paquete final re-auditado: 8/8 PASS.

## Correcciones del arnés detectadas por la propia auditoría

La primera corrida del arnés reportó 5/8. Las tres diferencias eran
defectos del ARNÉS, no del paquete, y se corrigen aquí declaradas:

- prereg hashes: el arnés comparaba bytes de archivo; el hash
  registrado usa el método congelado prereg_hash (sin created_utc).
  Con el método correcto, ambos preregs cuadran.
- marcadores: el barrido heurístico inicial incluía artifacts/ de
  datos congelados, fuera del alcance del ancla congelada.
- citaciones: la regex del arnés capturaba puntuación final.

## Checklist del agente (Anexo E)

- [x] SHA256SUMS_GAEA_V.txt cubre los 4 entregables; verificado tras
      el empaquetado final (sha256sum -c 4/4, dentro del arnés y por
      make package con verificación post-escritura).
- [x] .gitkeep en todos los dirs vacíos (barrido genérico en
      package_release); test_structure verde contra el ZIP extraído.
- [x] 14 anclas congeladas; la única modificación de identidad
      (atlas_git_head ecb494b -> 4427672, S-08) está registrada en
      docs/ANCHOR_CHANGES.md ANTES de datos, con re-hash encadenado.
- [x] config_sha256, suite_digest, prereg hashes, zoo baseline y
      champion tag encadenados en logs/audit.jsonl; audit_verify ok.
- [x] Manifiestos de todos los runs citados en los docs (paso 5 y 8).
- [x] README con tabla "Measured metrics" sin placeholders; lo no
      medido dice PENDIENTE con causa (FASE 7 de ATLAS, cloud null,
      atlas_int8).
- [x] FORBIDDEN_MARKERS verde; revisión manual del Anexo D (reglas
      operativas aplicadas en README, docs y commits: sin emojis,
      sin frases de relleno, bold solo técnico, commits de hechos).
- [x] Reproducción de humo: per_task.jsonl BIT-IDÉNTICO re-corriendo
      smoke_nano_solo (seed 42, mode nano, budget fast, max_iters 1)
      desde la extracción con hermanos enlazados: 100/100 filas
      iguales byte a byte contra el run congelado 048e92241fa8.
      Evidencia adicional preexistente: los dos runs independientes
      de bench_nano_solo (preprobe y post) son bit-idénticos.
- [x] FASES 5-7 de ATLAS: FASE 5 (RFT) y FASE 6 (bench + linaje)
      ejecutadas y medidas por gaea_v; FASE 7 de ATLAS declarada
      PENDIENTE con causa (pertenece al prompt y gates de ATLAS).
      Nunca implícita.

## Conclusión

Los 8 pasos del auditor y los 9 ítems del agente están verdes con
evidencia mecánica citada. Cualquier fallo futuro al repetir esta
verificación vuelve al gate de la fase correspondiente, con el
incidente en la cadena (regla del Anexo E).
