# Engine Refactor Log

## 2026-03-17

### Batch 1
- Se agrego la bitacora de refactor para documentar cada bloque de cambios.

### Batch 2
- Se agregaron rutas canonicas para `engine/pipeline/context.py`, `engine/pipeline/result.py` y `engine/pipeline/debug_trace.py`.
- Se creo una capa flat de stages en `engine/pipeline/stages/` para acercar el flujo al esquema objetivo.
- Se modelaron `element`, `style`, `snapshot`, `color`, `palette` y `environmental_assessment` dentro de `engine/domain/models/`.
- Se agregaron `engine/domain/data/web_colors.py`, placeholders de `token`, `transformation`, `plmlr_model`, enums `types/*` y utils base.

### Batch 3
- Se agregaron adapters canonicos para browser:
  `engine/adapters/browser/prototype_renderer.py`
  `engine/adapters/browser/snapshot_analyzer.py`
- Se agrego el adapter canonico para file system:
  `engine/adapters/file_system/file_handler.py`
- `engine/pipeline/pipeline.py` ahora orquesta stages flat y usa los modelos canonicos del pipeline.
- Se dejaron wrappers de compatibilidad en:
  `engine/models/debug_trace.py`
  `engine/models/pipeline_context.py`
  `engine/models/pipeline_result.py`
  `engine/models/prototype_structural_extractor/snapshot_models.py`
  `engine/models/color_processing/color_processing_models.py`
  `engine/models/environmental_assessment/*`
  `engine/services/file_handling/*`
  `engine/services/prototype_structural_extractor/*`
  `engine/enums/core/web_colors.py`
- Se reapuntaron imports de stages y servicios principales para consumir la estructura canonica nueva.

### Pending
- Verificar imports rotos en tiempo de ejecucion.
- Revisar si conviene invertir tambien `engine/enums/scope/*` para que dejen de ser la implementacion fuente.
- Consolidar mas helpers de `services/prototype_structural_extractor/` si quieres reducir mas la fragmentacion.
