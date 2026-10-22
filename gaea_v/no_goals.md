# No-goals del proyecto (vinculantes)

- El evaluador mide; no mejora. Ningún commit de gaea_v modifica
  código de atlas/ o hephaestus/ (separación de duties): los cambios
  de ATLAS siguen los gates y anclas de ATLAS.
- Sin APIs externas ni nube en las mediciones: cloud_reference queda
  null salvo aprobación explícita del operador, y si algún día se
  activa, es columna "solo referencia", nunca condición de inferencia.
- Sin cifras fuera de manifiesto: si un número no tiene run_id, no
  existe.
- TDA observa, nunca optimiza (heredado de V2.1). Los sensores
  topológicos son veto post-hoc, no gradiente.
- No competir en ppl bruta; no matar transformers; no inventar
  arquitectura sin evidencia; no reorientar ATLAS (no-goals de GAEA,
  heredados por el arnés).
- Sensor ausente no es sensor conforme; sensor descalibrado no es
  sensor neutral: se desactiva con causa.
- Sin recompensas no verificables: nada en este proyecto usa
  auto-evaluación del modelo como señal de entrenamiento sin pasar
  por el verificador compuesto.
- Gobernanza de sí mismo prohibida: gaea_v no se reescribe a sí
  mismo; su propio código cambia solo por review + tests + anclas,
  como cualquier commit.
