# Inventario inicial y clasificación (P1)

Este documento captura el estado actual de los archivos y la propuesta de ubicación dentro de la arquitectura acordada.
El objetivo es moverlos por responsabilidad real (IO, análisis, rendering, métricas, recomendaciones, transformación) y no por costumbre.

## Capa web (`app/`)
- `app.py` → `app/app.py` (entrypoint Flask, configuración web).
- `routes/main_routes.py` → `app/routes/main_routes.py` (orquestación HTTP).
- `templates/` → `app/templates/` (vistas HTML).
- `static/` → `app/static/` (recursos estáticos).
- `config.py` → `app/config.py` (configuración web, archivo único).

> Nota clave: actualmente `routes/main_routes.py` contiene parte del pipeline principal (orquesta análisis, rendering,
> métricas y recomendaciones). Ese pipeline se moverá gradualmente a `engine/core/pipeline/` sin romper el flujo.

## Motor (`engine/`)

### `engine/core/`
- Pipeline central que orquesta el flujo transversal del motor (coordinación de análisis/rendering/métricas).
- El pipeline actual existe en `utils/gui_pipeline.py` y se moverá a `engine/core/pipeline/`.
 - El pipeline actual en `routes/main_routes.py` se migrará por etapas para mantener el sistema funcional.

### `engine/file_handling/`
- `services/file_handler.py` → `engine/file_handling/services/` (validación y extracción de uploads).
- `services/session_cleaner.py` → `engine/file_handling/services/` (limpieza de sesiones temporales).
- `services/project_assets.py` → `engine/file_handling/services/` (copiado y normalización de recursos del proyecto).

### `engine/analysis/`
- `utils/html_parser.py` → `engine/analysis/utils/` (parsing HTML y extracción de componentes).
- Nuevas tareas futuras: inventario de estilos y análisis previo a optimización.

### `engine/rendering/`
- `utils/gui_analyzer.py` → `engine/rendering/services/` (renderizado de la GUI y captura).
- `utils/pixel_processor.py` → `engine/rendering/utils/` (extracción de pixeles).
- `utils/color_classifier.py` → `engine/rendering/utils/` (clasificación de color).
- Funciones relacionadas con análisis del DOM o screenshots deben vivir aquí.

### `engine/recommendations/`
- Este módulo se refactorizará al final por complejidad.
- `utils/colour_math.py` → `engine/recommendations/utils/` (si se usa para decisiones de recomendaciones).
- `utils/color_utils.py` → `engine/recommendations/utils/` (si se usa para recomendaciones).

### `engine/transformation/`
- Responsable de aplicar cambios sobre HTML/CSS/recursos, separado de la lógica de recomendaciones.
- Partes de `utils/heuristic_evaluator.py` que reescriben archivos irán aquí.

### `engine/metrics/`
- `utils/sci_rating.py` → `engine/metrics/services/`.
- `utils/evaluation_metrics.py` → `engine/metrics/services/` (si aplica).
- `utils/energy_calculator.py` → `engine/metrics/services/` (la lógica de cálculo se queda aquí).
  - El `EnergyModel` actual puede seguir usándose temporalmente hasta integrar `energy_model.json`.

### `engine/energy-model/`
- `energy_model.json` (modelo de datos consultable por métricas y recomendaciones).

## Workspace (`workspace/`)
- Las carpetas `input/`, `output/` y `artifacts/` viven dentro de cada sesión: `workspace/sessions/session_<key>/`.

## Tests (`tests/`)
- `utils/debug_logger.py` → `tests/debug/` (herramientas de traza/debug).

## Docs (`docs/`)
- Este archivo y documentación de arquitectura.

## Pipelines por módulo (plan)
- `engine/core/pipeline/`: pipeline central de orquestación.
- `engine/analysis/`: pipeline de análisis previo (HTML, inventarios, contexto para recomendaciones).
- `engine/rendering/`: pipeline de rendering (capturas "antes/después", conteo de pixeles, datos para métricas).
- `engine/metrics/`: pipeline de métricas (consumo, SCI, comparativas).
- `engine/file_handling/`: pipeline de ingreso/salida de archivos y sesiones.
- `engine/transformation/`: pipeline de transformación (aplicar cambios sobre fuentes).
- `engine/recommendations/`: pipeline de recomendaciones (reglas/criterios), a refactorizar al final.
