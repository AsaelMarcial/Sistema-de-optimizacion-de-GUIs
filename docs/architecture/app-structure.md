# Arquitectura vigente del engine

## Orquestación oficial

La entrada oficial del procesamiento es:

- `engine/pipeline/pipeline.py`

Su responsabilidad es orquestar stages, no implementar lógica de dominio directamente.

## Stages actuales

- `engine/pipeline/stages/file_handling/`
- `engine/pipeline/stages/prototype_structural_extractor/`
- `engine/pipeline/stages/environmental_assessment/`
- `engine/pipeline/stages/transformation/`
- `engine/pipeline/stages/color_processing/`
- `engine/pipeline/stages/recommendations/`
- `engine/pipeline/stages/results/`

Cada stage es un paquete con `__init__.py` + `stage.py` y, cuando hace falta, subpasos internos de coordinación.

## Capas raíz del runtime

- `engine/models`
  Modelos compartidos del runtime y legacy pasivo.
- `engine/services`
  Servicios reutilizables por dominio y servicios transversales.
- `engine/validators`
  Validaciones reales compartidas; actualmente solo `file_handling`.
- `engine/utils`
  Utilidades genéricas sin dominio; actualmente `html_utils.py`.

## Legacy pasivo

- `engine/models/legacy`
  Assets heredados de diccionarios y schemas conservados solo como referencia o compatibilidad pasiva.

## Convención de nombres

- Entrada pública del engine: `engine/pipeline/pipeline.py`
- Lógica reusable de dominio: `services/`
- Validaciones puras: `validators/`
- Modelos tipados: `models/`
- Utilidades genéricas sin dominio: `utils/`
- Si algo es reusable y de dominio, va al módulo de dominio o a `engine/services/`.
- Si algo solo coordina el runner, vive en `engine/pipeline/stages/<stage>/`.
- Si algo no tiene segundo consumidor real, no se promueve a una capa raíz.
- `engine/utils/` y `engine/validators/` raíz solo se crean cuando exista contenido transversal real; no se usan placeholders.
