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
- El pipeline actual existe en `engine/core/pipeline/gui_pipeline.py` (ubicación real verificada). ✅ Migrado.
- El pipeline actual en `routes/main_routes.py` se migrará por etapas para mantener el sistema funcional.

### `engine/file_handling/`
- `services/file_handler.py` → `engine/file_handling/services/` (validación y extracción de uploads). ✅ Migrado.
- `services/session_cleaner.py` → `engine/file_handling/services/` (limpieza de sesiones temporales). ✅ Migrado.
- `services/project_assets.py` → `engine/file_handling/services/` (copiado y normalización de recursos del proyecto). ✅ Migrado.

### `engine/analysis/`
- `utils/html_parser.py` → `engine/analysis/utils/` (parsing HTML y extracción de componentes). ✅ Migrado.
- `utils/file_manager.py` → `engine/analysis/utils/file_manager.py` (ubicación real verificada). ✅ Migrado.
- Nuevas tareas futuras: inventario de estilos y análisis previo a optimización.

### `engine/rendering/`
- `utils/gui_analyzer.py` → `engine/rendering/services/gui_analyzer.py` (ubicación real verificada; renderizado de la GUI y captura). ✅ Migrado.
- `utils/pixel_processor.py` → `engine/rendering/utils/pixel_processor.py` (ubicación real verificada; extracción de pixeles). ✅ Migrado.
- `utils/color_classifier.py` → `engine/rendering/utils/color_classifier.py` (ubicación real verificada; clasificación de color). ✅ Migrado.
- Funciones relacionadas con análisis del DOM o screenshots deben vivir aquí.

### `engine/recommendations/`
- Este módulo se refactorizará al final por complejidad.
- `utils/colour_math.py` → `engine/recommendations/utils/` (si se usa para decisiones de recomendaciones). ✅ Migrado.
- `utils/color_utils.py` → `engine/recommendations/utils/` (si se usa para recomendaciones). ✅ Migrado.

### `engine/transformation/`
- Responsable de aplicar cambios sobre HTML/CSS/recursos, separado de la lógica de recomendaciones.
- `utils/heuristic_evaluator.py` → `engine/transformation/services/` (aplicación de heurísticas y cambios sugeridos). ✅ Migrado.
- Adapter de heurísticas en `engine/transformation/heuristics.py`. ✅ Migrado.

### `engine/metrics/`
- `utils/sci_rating.py` → `engine/metrics/services/`. ✅ Migrado.
- `utils/evaluation_metrics.py` → `engine/metrics/services/evaluation_metrics.py` (ubicación real verificada). ✅ Migrado.
- `utils/energy_calculator.py` → `engine/metrics/services/energy_calculator.py` (ubicación real verificada; la lógica de cálculo se queda aquí). ✅ Migrado.
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
- `engine/analysis/utils/html_parser.py`.
- `engine/analysis/utils/file_manager.py`.
- `engine/metrics/services/sci_rating.py`.
- `engine/metrics/services/evaluation_metrics.py`.
- `engine/metrics/services/energy_calculator.py`.
- `engine/recommendations/utils/colour_math.py`.
- `engine/recommendations/utils/color_utils.py`.
- `engine/core/pipeline/gui_pipeline.py`.
- `engine/core/utils/debug_logger.py`.
- `engine/transformation/services/heuristic_evaluator.py`.
- `engine/transformation/heuristics.py`.

### Siguen en `utils/` (pendientes de migración)
- `utils/__pycache__/` (archivos residuales de ejecución).

### Rutas faltantes / por completar
- `engine/energy-model/energy_model.json` (pendiente: todavía no existe el archivo).

## Decisión de rutas finales (congelada)
Para evitar mover archivos dos veces, los módulos con un solo archivo principal vivirán directamente en su módulo
raíz (sin subcarpeta). Esta decisión queda congelada para la refactorización restante.

- `gui_pipeline` → `engine/core/gui_pipeline.py` (actual: `engine/core/pipeline/gui_pipeline.py`).
- `gui_analyzer` → `engine/rendering/gui_analyzer.py` (actual: `engine/rendering/services/gui_analyzer.py`).
- `color_classifier` → `engine/rendering/color_classifier.py` (actual: `engine/rendering/utils/color_classifier.py`).
- `pixel_processor` → `engine/rendering/pixel_processor.py` (actual: `engine/rendering/utils/pixel_processor.py`).
- `energy_calculator` → `engine/metrics/energy_calculator.py` (actual: `engine/metrics/services/energy_calculator.py`).
- `evaluation_metrics` → `engine/metrics/evaluation_metrics.py` (actual: `engine/metrics/services/evaluation_metrics.py`).
- `file_manager` → `engine/analysis/file_manager.py` (actual: `engine/analysis/utils/file_manager.py`).

### Archivos detectados (inventario real)

**`utils/`**
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
- `engine/transformation/services/heuristic_evaluator.py`
- `engine/transformation/heuristics.py`
- `engine/transformation/models/.gitkeep`
- `engine/transformation/validators/.gitkeep`
- `engine/transformation/utils/.gitkeep`
- `engine/energy-model/.gitkeep`
- `engine/analysis/services/.gitkeep`
- `engine/analysis/models/.gitkeep`
- `engine/analysis/validators/.gitkeep`
- `engine/analysis/utils/.gitkeep`
- `engine/analysis/utils/html_parser.py`
- `engine/analysis/utils/file_manager.py`
- `engine/metrics/services/.gitkeep`
- `engine/metrics/services/energy_calculator.py`
- `engine/metrics/services/evaluation_metrics.py`
- `engine/metrics/services/sci_rating.py`
- `engine/metrics/models/.gitkeep`
- `engine/metrics/validators/.gitkeep`
- `engine/metrics/utils/.gitkeep`
- `engine/core/pipeline/.gitkeep`
- `engine/core/pipeline/gui_pipeline.py`
- `engine/core/models/.gitkeep`
- `engine/core/validators/.gitkeep`
- `engine/core/utils/.gitkeep`
- `engine/core/utils/debug_logger.py`
- `engine/recommendations/utils/colour_math.py`
- `engine/recommendations/utils/color_utils.py`

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
- `engine/core/utils/debug_logger.py` (herramientas de traza/debug reutilizadas por la web).

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
