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

### Batch 4
- `engine/adapters/file_system/types.py` paso a ser el contrato canonico para `SessionWorkspace` y `ProjectInput`.
- `engine/pipeline/types.py` paso a ser el contrato canonico para `RecommendationsPayload`.
- `engine/models/file_handling/*` y `engine/models/recommendations/*` quedaron como wrappers de compatibilidad.
- Se movieron utilidades canonicas:
  `engine/adapters/utils/io.py`
  `engine/adapters/utils/filesystem.py`
  `engine/adapters/utils/serialization.py`
  `engine/adapters/utils/image_arrays.py`
  `engine/domain/utils/color_utils.py`
  `engine/domain/utils/coloraide.py`
- `engine/utils/file_utils.py`, `engine/utils/fs_utils.py`, `engine/utils/serialization_utils.py`,
  `engine/utils/image_utils.py`, `engine/utils/color_utils.py` y `engine/utils/coloraide_utils.py`
  quedaron como wrappers hacia las rutas canonicas nuevas.

### Batch 5
- Se invirtio `engine/enums/scope/*`: ahora la implementacion fuente vive en:
  `engine/domain/enums/scope/css_properties.py`
  `engine/domain/enums/scope/html_elements.py`
- `engine/enums/scope/css_properties.py` y `engine/enums/scope/html_elements.py`
  quedaron como wrappers legacy.
- La logica real de browser/snapshot se movio a:
  `engine/adapters/browser/layout_snapshot.py`
  `engine/adapters/browser/style_trace.py`
  `engine/adapters/browser/page_stability.py`
  `engine/adapters/browser/render_io.py`
  `engine/domain/utils/parsers.py`
- `engine/adapters/browser/prototype_renderer.py` y
  `engine/adapters/browser/snapshot_analyzer.py`
  ya consumen las rutas canonicas nuevas.
- `engine/services/prototype_structural_extractor/*` quedo reducido a wrappers de compatibilidad.

### Batch 6
- Color processing quedo cortado hacia rutas canonicas:
  `engine/domain/utils/palette_analysis.py`
  `engine/domain/data/material_quantization.py`
  `engine/adapters/utils/palette_preview.py`
  `engine/adapters/utils/pixel_frequency.py`
- `engine/services/color_processing/*` ahora reexporta esas implementaciones canonicas.
- `engine/pipeline/stages/color_processing/stage.py` ya consume dominio/adapters canonicos en lugar de `services/*`.

### Batch 7
- `engine/adapters/file_system/code_processor.py` paso a concentrar:
  staging de assets,
  lectura del HTML transformado,
  aplicacion de heuristicas.
- `engine/services/transformation/heuristic_evaluator.py` quedo como wrapper de compatibilidad.
- Los stages de `engine/pipeline/stages/transformation/*` ya consumen `code_processor.py`.

### Batch 8
- La logica de evaluacion ambiental se movio a `engine/domain/utils/environmental.py`.
- `engine/services/environmental_assessment/*` quedo como wrapper.
- `engine/pipeline/stages/environmental_assessment/stage.py` ya consume dominio canonico.

### Batch 9
- Se eliminaron wrappers muertos que el repo ya no consumia:
  `engine/models/pipeline_result.py`
  `engine/models/file_handling/project_input.py`
  `engine/models/file_handling/session_workspace.py`
  `engine/models/recommendations/recommendations_payload.py`
  `engine/services/file_handling/session_handler.py`
  `engine/services/prototype_structural_extractor/layout_snapshot_service.py`
  `engine/services/prototype_structural_extractor/page_stabilization_service.py`
  `engine/services/prototype_structural_extractor/render_io_service.py`
  `engine/services/prototype_structural_extractor/snapshot_normalization_service.py`
  `engine/services/prototype_structural_extractor/style_trace_service.py`
  `engine/services/transformation/heuristic_evaluator.py`
  `engine/services/environmental_assessment/assessment_service.py`
  `engine/services/environmental_assessment/energy_profile_service.py`
- Se intento remover tambien varios archivos legacy de `engine/utils/` y `engine/models/debug_trace.py`, pero el smoke suite actual todavia exige que existan como artefactos de compatibilidad.
- Por eso se dejaron solo los shims minimos necesarios en:
  `engine/models/debug_trace.py`
  `engine/utils/file_utils.py`
  `engine/utils/fs_utils.py`
  `engine/utils/serialization_utils.py`
  `engine/utils/image_utils.py`
  `engine/utils/color_utils.py`
  `engine/utils/html_utils.py`
  `engine/services/prototype_structural_extractor/page_capture_service.py`

### Batch 10
- `engine/domain/models/style.py` ahora define modelos ricos para:
  `StyleSourceRangeModel`
  `StyleDeclarationModel`
  `ComputedStyleValueModel`
  `StyleInventoryEntry`
- `engine/domain/models/element.py` ahora define modelos ricos para:
  `ElementAbsoluteBoundsModel`
  `ElementLayoutModel`
  `ElementIdentityModel`
  `ElementStyleStateModel`
  `ElementFlagsModel`
  `ElementInventoryEntry`
- `engine/domain/models/color.py` ahora define tambien:
  `SnapshotPaletteUsageModel`
  `SnapshotPaletteColorModel`
- `engine/domain/models/snapshot.py` ya usa `StyleInventoryEntry` y `SnapshotPaletteColorModel` en lugar de tuplas de diccionarios sueltos.
- `engine/domain/models/transformation.py` dejo de ser placeholder y ahora tiene:
  `TransformationTargetModel`
  `TransformationModel`
- `engine/domain/utils/parsers.py` y `engine/domain/utils/palette_analysis.py`
  ya aceptan y construyen estos modelos sin alterar la salida serializada actual.

### Batch 11
- Se elimino la compatibilidad legacy restante y el repo dejo de depender de:
  `engine/models/*`
  `engine/services/*`
  `engine/utils/*`
  `engine/enums/*`
  `engine/adapters/file_system/types.py`
  `engine/pipeline/types.py`
  `engine/domain/utils/environmental.py`
  `engine/adapters/utils/serialization.py`
  `engine/adapters/utils/image_arrays.py`
  `engine/adapters/utils/pixel_frequency.py`
- `SessionWorkspace` y `ProjectInput` quedaron absorbidos en:
  `engine/adapters/file_system/file_handler.py`
- `RecommendationsPayload` quedo absorbido en:
  `engine/pipeline/context.py`
- La evaluacion ambiental se reclasifico:
  la configuracion del modelo energetico vive en
  `engine/domain/models/environmental_assessment/energy_consumption.py`
  y el calculo de assessment completo en
  `engine/domain/models/environmental_assessment/carbon_footprint.py`
  mientras la orquestacion quedo en
  `engine/pipeline/stages/environmental_assessment/stage.py`
- `engine/adapters/utils/io.py` ahora concentra tambien `json_default_numpy_serializer`.
- Se consolido screenshot processing en:
  `engine/adapters/utils/screenshot.py`
  con `load_image_array`, `pixels_to_color_records` y `pixels_to_color_frequency`.
- `engine/domain/models/color.py` se adelgazo y ya no contiene:
  `PixelColorFrequency`
  `PixelColorStatistic`
  `SnapshotPaletteUsageModel`
  `SnapshotPaletteColorModel`
- `ToneStopModel` se movio a:
  `engine/domain/models/palette.py`
- `engine/domain/models/snapshot.py` ahora usa contratos tipados simples para la paleta del snapshot
  en lugar de modelos falsos intermedios.
- Se agrego:
  `engine/domain/enums/scope/json_exports.py`
  como export util canonico para payloads de scope.
- Se agrego:
  `engine/adapters/browser/style_trace_contracts.py`
  para tipar payloads repetidos de `style_trace.py` sin mover su algoritmo fuera del adapter.
- Se actualizaron consumidores externos reales:
  `tests/test_engine_refactor_smoke.py`
  `workspace/generated_web_colors.py`
- Resultado de validacion:
  `python -m unittest tests.test_engine_refactor_smoke` -> `40 tests OK`
  `rg -n "engine\\.(models|services|utils|enums)\\." engine app tests` -> sin coincidencias

### Pending
- Implementar `engine/pipeline/stages/build_inventories.py` y `engine/pipeline/stages/update_inventories.py`.
- Seguir endureciendo los modelos de snapshot:
  `engine/domain/models/element.py`
  `engine/domain/models/style.py`
  `engine/domain/models/color.py`
  `engine/domain/models/palette.py`
  `engine/domain/models/snapshot.py`
- Definir validacion de frontera para snapshot crudo antes de convertirlo a modelos.
- Evaluar si `PipelineContext` debe partirse por subestados cuando inventarios ya existan.
- Simplificar mas adelante los stages flat que hoy solo delegan a subpackages.
- Mantener fuera de alcance por ahora:
  `engine/pipeline/stages/set_tokens.py`
  `engine/pipeline/stages/check_tokens.py`
  `engine/domain/models/token.py`
  `engine/domain/data/plmlr_model.py`

### Batch 12
- `engine/domain/data/web_colors.py` absorbio por completo el contenido generado de colores web y ahora es la unica fuente de verdad para:
  `MultiValueEnum`
  `WebColorGroup`
  `WebColorMatch`
  `WebColor`
  `iter_web_colors`
  `get_web_color`
  `nearest_web_color`
- Se elimino:
  `workspace/generated_web_colors.py`
- `engine/domain/utils/colors.py` fue removido; los consumidores canonicos ahora importan directo desde:
  `engine/domain/utils/coloraide.py`
- `engine/pipeline/stages/` quedo totalmente plano. Se removieron las carpetas:
  `color_processing/`
  `environmental_assessment/`
  `file_handling/`
  `prototype_structural_extractor/`
  `recommendations/`
  `results/`
  `transformation/`
- La documentacion tecnica que vivia dentro de un stage eliminado se preservo en:
  `engine/legacy/prototype_structural_extractor_module1_snapshot_design.md`
- Los archivos flat absorbieron la orquestacion que antes estaba fragmentada:
  `process_file.py`
  `analyze_initial_state.py`
  `build_color_schema.py`
  `estimate_original_carbonfootprint.py`
  `estimate_savings.py`
  `apply_transformations.py`
  `report_obtained_results.py`
- El bundling de salida se movio al adapter:
  `engine/adapters/file_system/file_handler.py`
  mediante `create_output_bundle(...)`
- El contrato interno de stages quedo normalizado a:
  `run_*_stage(context: PipelineContext) -> PipelineContext`
- `engine/pipeline/pipeline.py` ahora reasigna el contexto devuelto por cada stage:
  `context = stage_runner(context)`
- Los placeholders flat tambien quedaron alineados al mismo contrato:
  `build_inventories.py`
  `update_inventories.py`
  `set_tokens.py`
  `check_tokens.py`
- Se actualizo:
  `tests/test_engine_refactor_smoke.py`
  para validar la topologia flat y la ausencia de las carpetas nested.
- Resultado de validacion:
  `python -m unittest tests.test_engine_refactor_smoke` -> `41 tests OK`
  `engine/pipeline/stages/` contiene solo archivos flat.

### Batch 13
- Se elimino la duplicacion entre contracts de `style_trace` y los modelos reales de estilo:
  `engine/adapters/browser/style_trace_contracts.py` fue removido.
- `engine/adapters/browser/style_trace.py` ahora exporta inventario de estilos con:
  `engine/domain/models/style.py`
  usando `StyleInventoryEntry`.
- `engine/adapters/browser/style_trace.py` ahora resuelve `computed_styles` hacia:
  `ComputedStyleValueModel`
  en lugar de mantener otro schema paralelo para esa salida.
- `engine/domain/models/style.py` se limpio para que contenga solo semantica de estilos:
  `StyleSourceRangeModel`
  `StyleDeclarationModel`
  `ComputedStyleValueModel`
  `StyleInventoryEntry`
- Se movieron los modelos de uso de color fuera de `style.py` hacia:
  `engine/domain/models/color.py`
  con:
  `TagUsageModel`
  `PropertyUsageModel`
- `engine/domain/models/color.py` ahora concentra tambien la construccion de evidencia semantica y confirmacion contra pixeles:
  `SnapshotColorEvidence.build(...)`
  `SnapshotColorEvidence.build_many(...)`
  `SnapshotColorEvidence.confirm_many(...)`
  `PixelColorRecord.build_many(...)`
- `engine/domain/models/palette.py` absorbio la construccion principal de familias y paletas, dejando la logica de palette donde corresponde:
  `PaletteFamilyModel`
  `CorePalettesModel.build(...)`
  `CorePalettesModel.map_evidences(...)`
  `TonalPaletteModel.from_family(...)`
  `PaletteAnalysisModel.build(...)`
- `engine/domain/utils/palette_analysis.py` quedo reducido a una fachada minima que delega a:
  `PaletteAnalysisModel.build(...)`
- `engine/domain/utils/parsers.py` y `engine/domain/models/element.py` se ajustaron para aceptar salidas modeladas desde `style_trace` sin volver a definir contratos paralelos.
- Resultado de validacion:
  `python -m unittest tests.test_engine_refactor_smoke` -> `41 tests OK`

### Batch 14
- Se reemplazo el `PipelineContext` plano por un contexto jerarquico con claves semanticas y API minima:
  `get(...)`
  `set(...)`
  `has(...)`
  `require(...)`
  `delete(...)`
  `snapshot(...)`
- Se agrego el contrato base de stages en:
  `engine/pipeline/stage_contract.py`
  con:
  `ContextValueSpec`
  `StageContract`
  `PipelineStage`
  `validate_requires(...)`
  `validate_produces(...)`
- `engine/pipeline/pipeline.py` ahora orquesta usando contratos por stage, validacion de `requires/produces` y trazas uniformes por etapa.
- Se renombraron los stages principales para reflejar mejor su responsabilidad:
  `process_file.py` -> `prepare_project_session.py`
  `analyze_initial_state.py` -> `capture_original_state.py`
  `build_color_schema.py` -> `build_color_scheme.py`
  `update_inventories.py` -> `enrich_color_inventory.py`
  `estimate_original_carbonfootprint.py` -> `assess_original_environmental_impact.py`
  `apply_transformations.py` -> `transform_source_project.py`
  `estimate_savings.py` -> `assess_transformed_environmental_impact.py`
  `report_obtained_results.py` -> `assemble_results.py`
- Los archivos legacy de stages anteriores fueron eliminados; la carpeta flat de stages ya no mantiene topologia duplicada.
- Se reforzo la observabilidad del pipeline en:
  `engine/pipeline/debug_trace.py`
  agregando:
  `add_stage_event(...)`
- Se agregaron validadores flat de frontera en:
  `engine/validators/snapshot_validators.py`
  `engine/validators/palette_validators.py`
- La construccion del esquema cromatico ya no guarda `pixel_color_statistics` como estado canonico del contexto; ese conteo se deriva cuando hace falta para trazas o resultados.
- Se saco `url_for` del pipeline. La etapa final ahora produce paths/bundle y:
  `app/routes.py`
  recompone el URL web antes de renderizar la plantilla.
- Se normalizo el nombre visible de la paleta acromatica a:
  `Neutral`
  desde:
  `engine/domain/models/palette.py`
  y se alinearon:
  `engine/adapters/utils/palette_preview.py`
  `app/templates/results.html`
- `engine/adapters/file_system/code_processor.py` ya no importa matematica de color desde:
  `engine/domain/utils/color_utils.py`
  sino desde:
  `engine/domain/utils/coloraide.py`
  dejando `color_utils.py` mas cerca de helpers CSS/string.
- `tests/test_engine_refactor_smoke.py` se actualizo para validar:
  contexto jerarquico,
  nombres nuevos de stage,
  export de `CONTRACT`,
  y naming `Neutral` en la vista derivada.

### Batch 15
- Se ajusto el ownership de estados de sesion para reflejar mejor:
  `input`
  `output`
  `artifacts`
  dentro de:
  `engine/domain/models/session.py`
  agregando:
  `ProjectStateModel`
  `ArtifactGroupModel`
  `SessionArtifactsModel`
  sin romper el `SessionModel` de workspace ya usado por file handling.
- El snapshot quedo limitado al estado inicial. En:
  `engine/domain/models/snapshot.py`
  `RenderSnapshot` ya no serializa:
  `elements_inventory`
  `styles_inventory`
  `palette`
  y ahora persiste solo:
  `metadata`
  `document`
  `nodes`
  `tree`
- `engine/domain/utils/parsers.py` dejo de construir inventarios dentro del artifact de snapshot.
  Ahora entrega nodos normalizados y payload derivable, mientras los inventarios se construyen aparte.
- `engine/pipeline/stages/build_inventories.py` paso a construir de verdad:
  `elements.inventory`
  `style.inventory`
  `color.inventory`
  desde el snapshot original, y persiste artifacts separados:
  `elements_inventory_original.json`
  `styles_inventory_original.json`
  `colors_inventory_original.json`
- Se separaron dos flujos de pixeles en:
  `engine/adapters/utils/screenshot.py`
  manteniendo:
  `pixels_to_color_frequency(...)`
  para el crudo de assessment
  y agregando:
  `pixels_to_display_color_records(...)`
  `pixels_to_display_color_frequency(...)`
  `cluster_color_records(...)`
  para predominancia visual.
- `engine/domain/models/color.py` ahora soporta enriquecimiento del inventario con evidencia del screenshot filtrado:
  `declared_in_snapshot`
  `added_from_pixel_evidence`
  `display_pixel_count`
  `display_pixel_percentage`
  `clustered_from_display_pixels`
- `engine/pipeline/stages/enrich_color_inventory.py` cambio de responsabilidad:
  ya no mapea a paletas;
  ahora enriquece `color.inventory` con evidencia display del screenshot original.
- Se agrego el stage nuevo:
  `engine/pipeline/stages/map_color_inventory_to_scheme.py`
  para separar el mapeo de inventario -> paleta/tono de la etapa de enriquecimiento.
- El orden real del pipeline en:
  `engine/pipeline/pipeline.py`
  ahora es:
  `prepare_project_session`
  `capture_original_state`
  `assess_original_environmental_impact`
  `build_inventories`
  `enrich_color_inventory`
  `build_color_scheme`
  `map_color_inventory_to_scheme`
  `transform_source_project`
  `assess_transformed_environmental_impact`
  `assemble_results`
- La preparacion del esquema cromatico salio de:
  `engine/domain/models/palette.py`
  y se movio a:
  `engine/domain/utils/palette_analysis.py`
  `palette.py` quedo como dueño de:
  paletas tonales,
  estructura de paletas,
  esquema dinamico,
  empaquetado de `PaletteAnalysisModel`.
- `engine/pipeline/stages/build_color_scheme.py` ahora consume:
  `color.inventory`
  `session.artifacts.original.pixel_frequencies_display`
  y ya no usa el crudo de pixeles para construir el esquema.
- El output ya no genera snapshot. En:
  `engine/adapters/browser/snapshot_analyzer.py`
  se agrego:
  `capture_render_screenshot_and_color_frequencies(...)`
  y:
  `engine/pipeline/stages/assess_transformed_environmental_impact.py`
  ahora persiste solo screenshot final y frecuencias crudas del output.
- Se modelaron los assessments ambientales en:
  `engine/domain/models/environmental_assessment/assessment.py`
  con:
  `EnvironmentalAssessmentModel`
  `EnvironmentalSavingsModel`
  y los stages ambientales / resultados dejaron de pasar `dicts` sueltos.
- `engine/pipeline/stages/transform_source_project.py` y
  `engine/pipeline/stages/assemble_results.py`
  ahora mantienen actualizado:
  `session.output.project`
  para que input y output compartan el mismo tipo de estado de proyecto.
- Se reforzo el contrato base con validadores reutilizables en:
  `engine/pipeline/stage_contract.py`
  y se restringieron namespaces top-level de contexto en:
  `engine/pipeline/context.py`
- `tests/test_engine_refactor_smoke.py` se actualizo al nuevo shape:
  snapshot crudo con `nodes/tree`,
  inventarios derivados aparte,
  stage nuevo de mapping,
  y pipeline sin snapshot del output.
- Resultado de validacion:
  `python -m unittest tests.test_engine_refactor_smoke` -> `45 tests OK`
