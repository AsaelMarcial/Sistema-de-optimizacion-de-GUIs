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
- `services/file_handler.py` → `engine/file_handling/services/` (validación y extracción de uploads). ✅ Migrado.
- `services/session_cleaner.py` → `engine/file_handling/services/` (limpieza de sesiones temporales). ✅ Migrado.
- `services/project_assets.py` → `engine/file_handling/services/` (copiado y normalización de recursos del proyecto). ✅ Migrado.

### `engine/analysis/`
- `utils/html_parser.py` → `engine/analysis/utils/` (parsing HTML y extracción de componentes). ⏳ Pendiente (sigue en `utils/`).
- Nuevas tareas futuras: inventario de estilos y análisis previo a optimización.

### `engine/rendering/`
- `utils/gui_analyzer.py` → `engine/rendering/services/` (renderizado de la GUI y captura). ✅ Migrado.
- `utils/pixel_processor.py` → `engine/rendering/utils/` (extracción de pixeles). ✅ Migrado.
- `utils/color_classifier.py` → `engine/rendering/utils/` (clasificación de color). ✅ Migrado.
- Funciones relacionadas con análisis del DOM o screenshots deben vivir aquí.

### `engine/recommendations/`
- Este módulo se refactorizará al final por complejidad.
- `utils/colour_math.py` → `engine/recommendations/utils/` (si se usa para decisiones de recomendaciones). ⏳ Pendiente (sigue en `utils/`).
- `utils/color_utils.py` → `engine/recommendations/utils/` (si se usa para recomendaciones). ⏳ Pendiente (sigue en `utils/`).

### `engine/transformation/`
- Responsable de aplicar cambios sobre HTML/CSS/recursos, separado de la lógica de recomendaciones.
- Partes de `utils/heuristic_evaluator.py` que reescriben archivos irán aquí. ⏳ Pendiente (sigue en `utils/`).

### `engine/metrics/`
- `utils/sci_rating.py` → `engine/metrics/services/`. ⏳ Pendiente (sigue en `utils/`).
- `utils/evaluation_metrics.py` → `engine/metrics/services/` (si aplica). ⏳ Pendiente (sigue en `utils/`).
- `utils/energy_calculator.py` → `engine/metrics/services/` (la lógica de cálculo se queda aquí). ⏳ Pendiente (sigue en `utils/`).
  - El `EnergyModel` actual puede seguir usándose temporalmente hasta integrar `energy_model.json`.

### `engine/energy-model/`
- `energy_model.json` (modelo de datos consultable por métricas y recomendaciones).

## Estado actual

### Migrados explícitamente (ya en `engine/`)
- `engine/rendering/services/gui_analyzer.py` (desde `utils/gui_analyzer.py`).
- `engine/rendering/utils/color_classifier.py` (desde `utils/color_classifier.py`).
- `engine/rendering/utils/pixel_processor.py` (desde `utils/pixel_processor.py`).
- `engine/file_handling/services/file_handler.py`.
- `engine/file_handling/services/session_cleaner.py`.
- `engine/file_handling/services/project_assets.py`.

### Siguen en `utils/` (pendientes de migración)
- `utils/file_manager.py`
- `utils/sci_rating.py`
- `utils/evaluation_metrics.py`
- `utils/energy_calculator.py`
- `utils/debug_logger.py`
- `utils/color_utils.py`
- `utils/gui_pipeline.py`
- `utils/heuristic_evaluator.py`
- `utils/html_parser.py`
- `utils/colour_math.py`

### Rutas faltantes / por completar
- `engine/analysis/utils/html_parser.py` (pendiente: `utils/html_parser.py`).
- `engine/metrics/services/` (pendiente: `utils/sci_rating.py`, `utils/evaluation_metrics.py`, `utils/energy_calculator.py`).
- `engine/recommendations/utils/` (pendiente: `utils/colour_math.py`, `utils/color_utils.py`).
- `engine/transformation/services/` (pendiente: porciones de `utils/heuristic_evaluator.py`).
- `engine/core/pipeline/` (pendiente: `utils/gui_pipeline.py` y la orquestación en `routes/main_routes.py`).
- `engine/energy-model/energy_model.json` (pendiente: todavía no existe el archivo).

### Archivos detectados (inventario real)

**`utils/`**
- `utils/file_manager.py`
- `utils/sci_rating.py`
- `utils/evaluation_metrics.py`
- `utils/energy_calculator.py`
- `utils/debug_logger.py`
- `utils/color_utils.py`
- `utils/gui_pipeline.py`
- `utils/heuristic_evaluator.py`
- `utils/html_parser.py`
- `utils/colour_math.py`
- `utils/__pycache__/evaluation_metrics.cpython-312.pyc`
- `utils/__pycache__/pixel_processor.cpython-314.pyc`
- `utils/__pycache__/colour_math.cpython-314.pyc`
- `utils/__pycache__/html_parser.cpython-314.pyc`
- `utils/__pycache__/gui_pipeline.cpython-314.pyc`
- `utils/__pycache__/html_parser.cpython-312.pyc`
- `utils/__pycache__/color_classifier.cpython-312.pyc`
- `utils/__pycache__/file_manager.cpython-312.pyc`
- `utils/__pycache__/color_utils.cpython-312.pyc`
- `utils/__pycache__/colour_math.cpython-312.pyc`
- `utils/__pycache__/heuristic_evaluator.cpython-314.pyc`
- `utils/__pycache__/color_classifier.cpython-314.pyc`
- `utils/__pycache__/dark_mode_manager.cpython-312.pyc`
- `utils/__pycache__/heuristic_evaluator.cpython-312.pyc`
- `utils/__pycache__/debug_logger.cpython-314.pyc`
- `utils/__pycache__/pixel_processor.cpython-312.pyc`
- `utils/__pycache__/sci_rating.cpython-314.pyc`
- `utils/__pycache__/color_utils.cpython-314.pyc`
- `utils/__pycache__/gui_analyzer.cpython-312.pyc`
- `utils/__pycache__/energy_calculator.cpython-312.pyc`
- `utils/__pycache__/gui_analyzer.cpython-314.pyc`
- `utils/__pycache__/energy_calculator.cpython-314.pyc`

**`engine/*`**
- `engine/recommendations/rules/.gitkeep`
- `engine/recommendations/services/.gitkeep`
- `engine/recommendations/models/.gitkeep`
- `engine/recommendations/validators/.gitkeep`
- `engine/recommendations/utils/.gitkeep`
- `engine/rendering/services/gui_analyzer.py`
- `engine/rendering/services/.gitkeep`
- `engine/rendering/models/.gitkeep`
- `engine/rendering/validators/.gitkeep`
- `engine/rendering/utils/.gitkeep`
- `engine/rendering/utils/color_classifier.py`
- `engine/rendering/utils/pixel_processor.py`
- `engine/file_handling/services/.gitkeep`
- `engine/file_handling/services/session_cleaner.py`
- `engine/file_handling/services/file_handler.py`
- `engine/file_handling/services/project_assets.py`
- `engine/file_handling/validators/.gitkeep`
- `engine/file_handling/utils/.gitkeep`
- `engine/transformation/services/.gitkeep`
- `engine/transformation/models/.gitkeep`
- `engine/transformation/validators/.gitkeep`
- `engine/transformation/utils/.gitkeep`
- `engine/energy-model/.gitkeep`
- `engine/analysis/services/.gitkeep`
- `engine/analysis/models/.gitkeep`
- `engine/analysis/validators/.gitkeep`
- `engine/analysis/utils/.gitkeep`
- `engine/metrics/services/.gitkeep`
- `engine/metrics/models/.gitkeep`
- `engine/metrics/validators/.gitkeep`
- `engine/metrics/utils/.gitkeep`
- `engine/core/pipeline/.gitkeep`
- `engine/core/models/.gitkeep`
- `engine/core/validators/.gitkeep`
- `engine/core/utils/.gitkeep`

**`app/`**
- `app/__init__.py`
- `app/static/.gitkeep`
- `app/static/images/logo-placeholder.svg`
- `app/static/corrected/efb76026/debug_original.png`
- `app/static/corrected/efb76026/assets/imagen-prueba.jpg`
- `app/static/corrected/efb76026/debug_optimized.png`
- `app/static/corrected/efb76026/styles/estilos.css`
- `app/static/corrected/efb76026/index.html`
- `app/static/corrected/9af2bafc.zip`
- `app/static/corrected/55f14742.zip`
- `app/static/corrected/3769ccc4.zip`
- `app/static/corrected/3769ccc4/debug_original.png`
- `app/static/corrected/3769ccc4/assets/imagen-prueba.jpg`
- `app/static/corrected/3769ccc4/debug_optimized.png`
- `app/static/corrected/3769ccc4/styles/estilos.css`
- `app/static/corrected/3769ccc4/index.html`
- `app/static/corrected/efb76026.zip`
- `app/static/corrected/a1b97957.zip`
- `app/static/corrected/55f14742/debug_original.png`
- `app/static/corrected/55f14742/assets/imagen-prueba.jpg`
- `app/static/corrected/55f14742/debug_optimized.png`
- `app/static/corrected/55f14742/styles/estilos.css`
- `app/static/corrected/55f14742/index.html`
- `app/static/corrected/index_corrected.html`
- `app/static/corrected/9af2bafc/imagenes/imagen-prueba.jpg`
- `app/static/corrected/9af2bafc/debug_original.png`
- `app/static/corrected/9af2bafc/menu.html`
- `app/static/corrected/9af2bafc/debug_optimized.png`
- `app/static/corrected/9af2bafc/css/estilos.css`
- `app/static/corrected/a1b97957/debug_original.png`
- `app/static/corrected/a1b97957/assets/imagen-prueba.jpg`
- `app/static/corrected/a1b97957/debug_optimized.png`
- `app/static/corrected/a1b97957/styles/estilos.css`
- `app/static/corrected/a1b97957/index.html`
- `app/static/css/styles.css`
- `app/static/js/scripts.js`
- `app/routes/.gitkeep`
- `app/routes/main_routes.py`
- `app/templates/.gitkeep`
- `app/templates/results.html`
- `app/templates/header.html`
- `app/templates/index.html`
- `app/__pycache__/config.cpython-314.pyc`
- `app/__pycache__/__init__.cpython-314.pyc`
- `app/config.py`
- `app/app.py`

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
