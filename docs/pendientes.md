# Pendientes de alineacion SRS

Fecha de auditoria inicial: 2026-04-11  
Ultima revision de estado: 2026-04-19  
Scope auditado: `engine/*` y referencias relevantes en `tests/*`.

## Resumen ejecutivo

- El `PipelineContext` ya esta alineado en roots principales y ya no debe guardar roots legacy como `inventory`, `elements` o `color`.
- `style.catalog` queda como root permitido para computed styles capturados por CDP/captureSnapshot.
- Atendido: ya no existe un modulo relacional paralelo de tokens como dependencia operativa ni verdad paralela.
- Atendido: los tokens ya se copian a instancias reales: `Element`, `Property` y colores de `scheme.colors`.
- Implementado: la parte de pixeles ya usa un unico contrato operativo `color_histogram`, sin `pixel_frequency`, sin stage `capture_display_pixels`, sin histogramas en `RenderArtifacts` y sin scalars globales de scheme.
- Nota SRS: `color_histogram` es el contrato implementado y testeado, pero los nombres normativos del SRS vigente siguen siendo `scheme.pixel_frequency` y `environmental.inputs.*.pixel_histogram`; queda pendiente ratificar este cambio en el SRS o renombrar el codigo.
- Deuda principal restante: `TokenInventory` aun debe terminar de degradarse a vista derivada; `ColorCatalog` sigue siendo una proyeccion operativa; `RenderArtifacts` sigue siendo DTO publico de adapter; `StyleCatalog` todavia necesita acotarse mejor; `Property` y `quality_reports` siguen usando strings donde ya existen enums; `css_overview` sigue siendo dependencia fuerte para contraste; y el dominio sigue aceptando demasiados `payload`.

## Estado almacenado en `PipelineContext`

Roots permitidos en `engine/pipeline/context.py`:

- `session`
- `prototype_structure`
- `style`
- `scheme`
- `token`
- `derived`
- `environmental`
- `transformation`
- `recommendations`
- `results`

Claves vivas por fase:

- `PipelineContext.__post_init__`
  - Guarda `session.input.file`.
- `prepare_project_session`
  - Lee `session.input.file`.
  - Guarda `session`.
- `start_page_builder`
  - Lee `session`.
  - Guarda `session.runtime.page_builder`.
- `capture_original_state`
  - Lee `session` y `session.runtime.page_builder`.
  - Captura screenshot, snapshot y css overview.
  - Guarda `session.runtime.original_capture` como transporte temporal de runtime.
  - Ya no genera histogramas.
- `capture_prototype_structure`
  - Lee `session.runtime.original_capture`.
  - Guarda `prototype_structure`.
  - Guarda `style.catalog`.
  - Guarda `derived.raw_css_overview` como dependencia transicional.
  - Guarda `derived.raw_snapshot_metadata`.
  - Elimina `session.runtime.original_capture` al terminar.
- `build_color_scheme`
  - Lee `prototype_structure`, `derived.raw_css_overview` y `session`.
  - Genera `environmental.before.color_histogram`.
  - Genera `scheme.color_histogram`.
  - Guarda `scheme.colors`.
  - Guarda `scheme.tonal_palettes`.
  - Guarda `scheme.named_color_breakdown`.
- `build_contrast_report`
  - Lee `prototype_structure`, `scheme.colors` y `derived.raw_css_overview`.
  - Guarda `derived.contrast_report`.
- `close_page_builder`
  - Lee y elimina `session.runtime.page_builder`.
  - Guarda `session.runtime.page_builder_closed`.
- `assess_original_environmental_impact`
  - Lee `environmental.before.color_histogram`.
  - Guarda `environmental.assessment.before`.
- `set_tokens`
  - Lee `prototype_structure`, `scheme.colors` y `scheme.tonal_palettes`.
  - Guarda `token.inventory`.
- `check_tokens`
  - Lee `prototype_structure`, `scheme.colors`, `scheme.tonal_palettes` y `token.inventory`.
  - Reescribe `token.inventory`.
- `transform_source_project`
  - Lee `session`, `prototype_structure` y `token.inventory`.
  - Guarda `transformation.heuristics`.
  - Guarda `transformation.output.html.path`.
  - Guarda `transformation.output.html.content`.
  - Reescribe `session` con `output_html_content`.
- `assess_transformed_environmental_impact`
  - Lee `session`, `transformation.output.html.content` y `environmental.assessment.before`.
  - Captura screenshot transformado.
  - Genera `environmental.after.color_histogram`.
  - Guarda `environmental.assessment.after`.
  - Guarda `environmental.assessment.savings`.
- `assemble_results`
  - Lee `session`, assessments ambientales, `environmental.before.color_histogram`, `scheme.colors`, `scheme.tonal_palettes`, `scheme.named_color_breakdown`, `token.inventory`, `derived.contrast_report` y `transformation.*`.
  - Guarda `recommendations`.
  - Guarda `results`.

## Estado dentro de `prototype_structure`

`prototype_structure` guarda:

- `nodes: tuple[Element, ...]`.
- `indexes: PrototypeIndexes`.
- `declaration_values`.
- caches privados:
  - `_node_by_id`
  - `_children_by_id`
  - `_depth_by_id`

Cada `Element` guarda:

- Identidad DOM: `node_id`, `backend_node_id`, `parent_id`, `children_ids`, `document_order`.
- Semantica DOM: `tag_name`, `node_name`, `html_id`, `name`, `role`, `class_names`, `data_attributes`, `attributes`, `selector`, `xpath`, `related_media`.
- Texto y pintura: `text`, `paint_order`.
- Layout plano: `x`, `y`, `width`, `height`, `left`, `top`, `right`, `bottom`.
- Flags: `is_visible`, `is_leaf`, `has_siblings`, `is_text_node`, `is_out_of_scope`, `is_stacking_context`.
- Evidencia CDP: `effective_background`.
- Propiedades resueltas: `properties`.
- Asignaciones de tokens: `token_ids`.

Cada `Property` guarda:

- `name`
- `value`
- `classification`
- `color_id`
- `style_id`
- `declaration_id`
- `declared_property`
- `inherited_from_element_id`
- `resolution_status`
- `authored_value`
- `token_ids`
- `applied_token_id`
- `token_alias_to`

Atendido:

- `PrototypeStructure` ya no expone `ColorCatalog`.
- La proyeccion cromatica vive fuera, en `engine/domain/utils/color_usage.py`.
- `PrototypeStructure.excluded_pixel_boxes()` usa `get_html_element`, `HtmlElementScopeGroup.OUT_OF_SCOPE_VISIBLE` y `MEDIA_METADATA_ONLY_TAGS`.
- Ya existen atributos de token en `Element`, `Property` y colores de `scheme.colors`.

Pendiente:

- `Property.name`, `declared_property`, `classification` y `resolution_status` aun son strings.
- Faltan queries directas para foreground/background/effect si se quiere reducir dependencia de `css_overview`.

## Verdades operativas actuales

- `PrototypeStructure`: verdad estructural de nodos, propiedades, navegacion, layout y resolucion efectiva.
- `scheme.colors`: verdad semantica de color interpretado por scheme.
- `scheme.color_histogram`: histograma visual del scheme, con exclusiones restadas y clusterizado.
- `environmental.before.color_histogram`: histograma completo del screenshot original para assessment ambiental.
- `environmental.after.color_histogram`: histograma completo del screenshot transformado para assessment ambiental.
- `scheme.tonal_palettes`: verdad de paletas y tonos.
- `token.inventory`: catalogo/vista de tokens generados; todavia conserva metadata relacional que deberia ser derivada desde instancias.
- `derived.raw_css_overview`: dependencia transicional para contrast issues y observed colors.
- `RenderArtifacts`: DTO transitorio de adapter guardado en `session.runtime.original_capture`, no en `Session`.
- `ColorCatalog`: proyeccion derivada usada como lookup operativo; no debe convertirse en verdad primaria.
- `StyleCatalog`: catalogo de computed styles devueltos por CDP/captureSnapshot; no debe representar CSS authored completo ni usage estructural competitivo.

## Ownership objetivo acordado

Flujo objetivo:

```text
upload/input
  -> Session
  -> PageBuilder captura screenshot y caracteristicas del diseno
       -> PrototypeStructure(Element + Property)
       -> StyleCatalog(computed styles CDP/captureSnapshot)
       -> evidencia de pixeles para environmental/scheme
       -> Scheme(colors + tonal palettes)
  -> Quality reports derivados de PrototypeStructure y Scheme
  -> Token assignments en Element/Property/SchemeColor
  -> Transformacion de codigo fuente
  -> environmental_assessment before/after
  -> Results para results.html
```

Reglas:

- `Session` guarda informacion estable de la sesion actual: id, base_dir, rutas y contenido necesario.
- `PageBuilder` es owner del browser/CDP y debe cerrarse despues de capturar los modelos finales.
- `style.catalog` guarda unicamente computed styles capturados por CDP/captureSnapshot.
- `prototype_structure` guarda DOM, relaciones, layout y propiedades resueltas minimas por nodo.
- `scheme` guarda colores semanticos, evidencia visual de pixeles y paletas tonales.
- `environmental` guarda evidencia completa before/after para assessment.
- Los effect colors se consultan desde `Property(classification="effect")`.
- Los tokens no crean una fuente primaria paralela: se agregan como atributos en `Element`, `Property` y `SchemeColor`.

## Pixeles y color evidence

Estado actual:

- `engine/adapters/utils/pixel.py` es el unico modulo operativo de pixeles.
- Contrato operativo implementado:

```python
[{"color": [r, g, b], "count": n}]
```

- `build_color_histograms(image_source, prototype_structure=None, cluster_distance=6.0)` devuelve:

```python
{"environmental": color_histogram, "scheme": color_histogram}
```

- `environmental.before.color_histogram` se genera una vez en `build_color_scheme`.
- `scheme.color_histogram` se genera desde el mismo screenshot original, restando `prototype_structure.excluded_pixel_boxes()` y clusterizando.
- `environmental.after.color_histogram` se genera en `assess_transformed_environmental_impact` desde el screenshot transformado.
- `assemble_results` calcula porcentajes con `dominant_color_percentages(environmental.before.color_histogram, limit=10)`.
- `Color.pixel_count` y `Color.pixel_percentage` se conservan porque alimentan pesos de paleta, named breakdown y evidencia por color.
- `PaletteFamilyModel.pixel_count` y `TonalPaletteModel.pixel_count` se conservan como pesos internos.

Nota de desviacion SRS:

- El codigo actual usa `scheme.color_histogram`, `environmental.before.color_histogram` y `environmental.after.color_histogram`.
- El SRS vigente todavia nombra estos branches como `scheme.pixel_frequency` y `environmental.inputs.*.pixel_histogram`.
- Hasta actualizar el SRS, `color_histogram` debe leerse como implementacion vigente, no como decision normativa final cerrada.

Atendido:

- Ya no existe `capture_display_pixels`.
- En codigo ya no existe `scheme.pixel_frequency`.
- Ya no existe `scheme.color_frequency`.
- Ya no existen `scheme.pixel_count`, `scheme.residual_pixel_count` ni `scheme.residual_distinct_colors`.
- Ya no existen `environmental.inputs.original.*` ni `environmental.inputs.output.*` para pixeles.
- Ya no existe `include_pixel_histogram`.
- `RenderArtifacts` ya no transporta histogramas.
- `PageBuilder` ya no calcula histogramas.
- `assess_original_environmental_impact` consume `environmental.before.color_histogram`.
- `assess_transformed_environmental_impact` usa `build_color_histograms`.
- `results` ya no serializa estadisticas intermedias muertas de pixeles.

Pendiente:

- Medir si `cluster_color_histogram` necesita optimizacion para screenshots con muchisimos colores unicos. Hoy no es deuda funcional; es una posible optimizacion de performance.
- Reducir aun mas la dependencia de `ColorCatalog` como proyeccion operativa cuando `scheme.colors` pueda actuar como lookup primario.
- Ratificar en el SRS si se conserva `color_histogram` como nombre final o si se renombra al contrato normativo `pixel_frequency` / `pixel_histogram`.

## Relaciones paralelas de tokens eliminadas

Estado actual:

- La rama legacy de relaciones de inventario ya no vive en `context`.
- Atendido: el antiguo helper relacional de tokens ya no vive en `engine/domain/utils`.
- Atendido: `engine/domain/utils/token.py` ya no requiere una estructura relacional paralela.
- Atendido: `engine/validators/token_rules.py` ya no requiere una estructura relacional paralela.
- Atendido: `set_tokens` y `check_tokens` operan sobre `prototype_structure + scheme.colors + scheme.tonal_palettes`, sin una rama paralela de relaciones.
- La transformacion final ya usa `prototype_structure + token.inventory` y no necesita una estructura relacional paralela.

Pendiente:

- Convertir `TokenInventory` en vista/export derivada.
- Evitar que `Token` sea owner primario de `assigned_element_ids`, `source_property_refs` y campos equivalentes.

## RenderArtifacts, ColorCatalog y StyleCatalog

`RenderArtifacts`:

- Ya no transporta histogramas.
- Sigue siendo un DTO publico de adapter usado como `session.runtime.original_capture`.
- Todavia transporta `styles_inventory_seed`, `colors_inventory_seed` y `css_overview`.

Pendiente:

- Eliminar `RenderArtifacts` como modelo publico/estable o moverlo a un resultado privado de adapter.
- Hacer que `PageBuilder` entregue modelos finales o un objeto de captura claramente privado.
- Eliminar `styles_inventory_seed` y `colors_inventory_seed` cuando `capture_prototype_structure` ya no dependa de semillas paralelas.

`ColorCatalog`:

- No debe ser verdad primaria.
- Actualmente es una proyeccion derivada para construir/consultar colores.

Pendiente:

- Absorber responsabilidades utiles en `scheme.colors`.
- Degradar o renombrar `ColorCatalog` como proyeccion derivada si se conserva.
- Evitar reconstruir `ColorCatalog` desde `scheme.colors` en varios stages.

`StyleCatalog`:

- Debe existir por si solo como catalogo de computed styles CDP/captureSnapshot.

Pendiente:

- Limitarlo a computed styles capturados.
- Eliminar usage estructural persistido si se deriva desde `PrototypeStructure`.
- Evitar que compita con `Property` como verdad de resolved style.

## Enums y data

Atendido:

- `engine/domain/data/css_properties.py` ya no existe como modulo operativo.
- Las definiciones CSS viven en `engine/domain/enums/scope/css_properties.py`.

Pendientes:

- Migrar `Property.name` a `CssPropertyId`.
- Migrar `Property.declared_property` a `CssPropertyId | None`.
- Migrar `Property.resolution_status` a `StyleResolutionStatus`.
- Eliminar strings libres de `Property.classification`.
- Derivar classification desde `CssColorRole` y `CssPropertyCategory`.
- Migrar `quality_reports.property_name` y `quality_reports.declared_property` a `CssPropertyId`.
- Evaluar si `Element.tag_name` debe migrar a `HtmlElementId` o mantenerse como string normalizado por compatibilidad con DOM real.

## Quality reports

Estado actual:

- Atendido: `EffectColorReport` ya no existe como rama `derived` ni stage del pipeline.
- `effect_colors` se derivan en `assemble_results` desde `PrototypeStructure.properties(classification="effect")` y `scheme.colors`.
- `ContrastReport` todavia depende de `derived.raw_css_overview["contrast_issues"]`.
- `quality_reports.py` usa strings para propiedades.

Pendiente:

- Decidir estrategia final de `ContrastReport`: mantener enrichment desde `css_overview` o implementar detector propio.
- Agregar queries en `PrototypeStructure` para foreground/background/effect.
- Agregar soporte tipografico si contraste deja de depender de `css_overview`.
- Asegurar que reports usen `CssPropertyId`.

## Payloads

Estado actual:

- El dominio sigue aceptando muchos `payload`/`payloads`.
- Varios modelos tienen `build(payload)` o `build_many(...)`.

Problema:

- Cada builder local normaliza distinto.
- Esto aumenta drift de schema, errores silenciosos y duplicacion de coerciones.

Pendiente:

- Dejar payloads solo en bordes:
  - adapters browser
  - adapters filesystem
  - serializacion final
  - parsing de entrada externa
- Dentro del dominio deben circular modelos tipados.
- Evitar `to_dict()` como input de logica interna.
- Crear factories explicitas por fuente:
  - `Element.from_cdp_node(...)`
  - `Property.from_resolved_style(...)`
  - `SchemeColor.from_color_usage(...)`
  - `Session.from_upload(...)`

## Checklist consolidado

### P0 - Eliminar relaciones paralelas

- [x] Eliminar el antiguo helper relacional de tokens en `engine/domain/utils`.
- [x] Quitar la dependencia relacional paralela de `engine/domain/utils/token.py`.
- [x] Quitar la dependencia relacional paralela de `engine/validators/token_rules.py`.
- [x] Quitar la dependencia relacional paralela de `set_tokens`.
- [x] Quitar la dependencia relacional paralela de `check_tokens`.
- [x] Eliminar serializers de relaciones paralelas en `artifact_serializers.py`.
- [x] Eliminar tests que construyen o validan estructuras relacionales paralelas.
- [x] Cambiar tokenizacion a `prototype_structure + scheme.colors + scheme.tonal_palettes`.

### P1 - Tokens como atributos de instancias

- [x] Agregar asignacion de tokens a `Property`.
- [x] Agregar asignacion de tokens a `Element`.
- [x] Agregar asignacion de tokens a `SchemeColor`.
- [ ] Convertir `TokenInventory` en vista/export derivada.
- [ ] Evitar que `Token` sea owner primario de relaciones ya presentes en instancias.
- [x] Ajustar `code_processor` para leer asignaciones desde `Property`.
- [x] Ajustar `assemble_results` para resumir asignaciones desde instancias.

### P2 - Color usages y Scheme

- [x] Sacar `build_color_inventory` de `PrototypeStructure`.
- [x] Sacar `build_observed_color_payloads` de `PrototypeStructure`.
- [ ] Absorber responsabilidades utiles de `ColorCatalog` en `scheme.colors`.
- [ ] Degradar o renombrar `ColorCatalog` como proyeccion derivada.
- [ ] Evitar reconstruir `ColorCatalog` desde `scheme.colors` en varios stages.
- [ ] Hacer que `scheme.colors` sea el lookup primario para reports/tokens.

### P3 - Pixeles

- [x] Centralizar pixeles en `engine/adapters/utils/pixel.py`.
- [x] Usar solo el formato `color_histogram`.
- [x] Generar `environmental.before.color_histogram`.
- [x] Generar `environmental.after.color_histogram`.
- [x] Generar `scheme.color_histogram`.
- [x] Eliminar `capture_display_pixels`.
- [x] Eliminar histogramas de `RenderArtifacts` y `PageBuilder`.
- [x] Eliminar `include_pixel_histogram`.
- [x] Eliminar scalars globales de scheme para pixeles/residuales.
- [x] Conservar `Color.pixel_count` como evidencia por color.
- [x] Derivar porcentajes de results desde `dominant_color_percentages`.
- [ ] Medir/optimizar clusterizacion por Delta E si aparece cuello de botella.

### P4 - Render/captura

- [x] Evitar guardar `original_capture` en `Session` como estado de dominio.
- [x] Quitar captura de histogramas del browser adapter.
- [x] Quitar `include_pixel_histogram`.
- [x] Quitar histogramas de `RenderArtifacts`.
- [ ] Eliminar `RenderArtifacts` como modelo publico/estable.
- [ ] Hacer que `PageBuilder` entregue modelos finales o un resultado privado de adapter.
- [ ] Eliminar `styles_inventory_seed` de `RenderArtifacts`.
- [ ] Eliminar `colors_inventory_seed` de `RenderArtifacts`.

### P5 - StyleCatalog

- [x] Mantener `StyleCatalog` como subdominio propio.
- [ ] Limitarlo a computed styles CDP/captureSnapshot.
- [ ] Eliminar usage estructural persistido si se deriva desde `PrototypeStructure`.
- [ ] Evitar que `StyleCatalog` compita con `Property` como verdad de resolved style.8igm 777o

### P6 - Enums

- [x] Dejar de usar `engine.domain.data.css_properties` en dominio core.
- [ ] Migrar `Property.name` a `CssPropertyId`.
- [ ] Migrar `Property.declared_property` a `CssPropertyId | None`.
- [ ] Migrar `Property.resolution_status` a `StyleResolutionStatus`.
- [ ] Migrar `quality_reports` a `CssPropertyId`.
- [ ] Eliminar strings libres de `classification`.
- [ ] Usar `CssColorRole` y `CssPropertyCategory` como fuente de clasificacion.

### P7 - Quality reports

- [x] Eliminar `derived.effect_color_report`.
- [x] Eliminar o desactivar `build_effect_color_report` como stage.
- [x] Si la UI necesita effects, derivarlos en `results` desde `PrototypeStructure` y `scheme.colors` sin nueva rama `derived`.
- [ ] Decidir estrategia final de `ContrastReport`.
- [ ] Agregar queries de foreground/background/effect en `PrototypeStructure`.
- [ ] Agregar soporte tipografico si contraste deja de depender de `css_overview`.

### P8 - Payloads

- [ ] Reducir builders `build(payload)` en modelos de dominio.
- [ ] Dejar payloads solo en adapters y serializacion.
- [ ] Cambiar factories genericas por factories especificas por fuente.
- [ ] Evitar `to_dict()` como input de logica interna.
- [ ] Agregar tests arquitectonicos para evitar nuevos payload builders en dominio core.

### P9 - Tests y arquitectura

- [x] Agregar test que falle si aparece una estructura relacional paralela en `engine/*`.
- [x] Agregar test que falle si aparece la rama legacy de relaciones de inventario.
- [x] Agregar test que falle si el antiguo helper relacional de tokens es importable.
- [x] Agregar test que valide que token assignments viven en `Property`/`Element`/`SchemeColor`.
- [x] Agregar test que valide que `prototype_structure` no importa `ColorCatalog`.
- [x] Agregar tests de `build_color_histograms`, exclusiones, clusterizacion, `get_color_count`, totales y porcentajes.
- [x] Agregar guardrails contra contratos legacy de pixeles.
- [ ] Agregar test que valide que `Property.name` es `CssPropertyId`.
- [ ] Agregar guardrails contra nuevos payload builders en dominio core.

## Orden recomendado actualizado

### Fase 1 - Convertir `TokenInventory` en vista derivada

Checklist cubierto: resto de `P1`.

Acciones:

- [ ] Definir si `TokenInventory` queda como vista exportable o catalogo secundario derivado.
- [ ] Evitar que `Token` sea owner primario de relaciones token-element-property-color.
- [ ] Revisar `code_processor`, `set_tokens`, `check_tokens` y tests para que las relaciones se lean desde instancias canonicas.
- [ ] Quitar fallbacks que reconstruyen ownership desde `Token.assigned_element_ids` o `Token.source_property_refs` cuando ya exista asignacion en `Element`, `Property` o `SchemeColor`.

### Fase 2 - Consolidar `scheme.colors` como lookup primario

Checklist cubierto: `P2`.

Acciones:

- [ ] Absorber responsabilidades utiles de `ColorCatalog` en `scheme.colors`.
- [ ] Degradar o renombrar `ColorCatalog` como proyeccion derivada.
- [ ] Evitar reconstrucciones repetidas de `ColorCatalog`.
- [ ] Hacer que reports/tokens consulten primero `scheme.colors`.

### Fase 3 - Tipar el dominio base

Checklist cubierto: `P6`, parte de `P5`, parte de `P7`.

Acciones:

- [ ] Migrar `Property.name` a `CssPropertyId`.
- [ ] Migrar `Property.declared_property` a `CssPropertyId | None`.
- [ ] Migrar `StyleResolutionStatus` a `Property.resolution_status`.
- [ ] Reemplazar `classification: str` por derivacion desde `CssColorRole` y `CssPropertyCategory`.
- [ ] Migrar `quality_reports.property_name` y `quality_reports.declared_property` a `CssPropertyId`.

### Fase 4 - Limpiar captura y `RenderArtifacts`

Checklist cubierto: `P4`.

Acciones:

- [ ] Eliminar `RenderArtifacts` como modelo publico/estable.
- [ ] Hacer que `PageBuilder` entregue modelos finales o un resultado privado de adapter.
- [ ] Eliminar `styles_inventory_seed`.
- [ ] Eliminar `colors_inventory_seed`.

### Fase 5 - Reacotar `StyleCatalog`

Checklist cubierto: `P5`.

Acciones:

- [ ] Mantenerlo como catalogo de computed styles CDP/captureSnapshot.
- [ ] Eliminar metadata authored/cascade/source si no viene de captureSnapshot o no es necesaria.
- [ ] Eliminar `node_ids`, `usage_count`, `used_by_element_ids` y `element_usage_count` si son derivables desde `PrototypeStructure`.

### Fase 6 - Alinear quality reports al canon final

Checklist cubierto: `P7`.

Acciones:

- [ ] Definir estrategia final de contraste.
- [ ] Agregar queries en `PrototypeStructure` para foreground/background/effect.
- [ ] Si se elimina `css_overview`, agregar soporte tipografico suficiente.
- [ ] Asegurar que reports usen `CssPropertyId`.

### Fase 7 - Reducir payloads

Checklist cubierto: `P8`.

Acciones:

- [ ] Mover payloads a bordes de adapters y serializacion.
- [ ] Reducir builders genericos `build(payload)` en modelos de dominio.
- [ ] Crear factories especificas por fuente.
- [ ] Evitar `to_dict()` como input de logica interna.

### Fase 8 - Cierre arquitectonico

Checklist cubierto: cierre transversal de `P0..P9`.

Acciones:

- [ ] Ejecutar barridos `rg` contra relaciones paralelas, `inventory`, `payload`, `ColorCatalog`, strings de properties y aliases legacy.
- [ ] Eliminar modulos sin callers.
- [ ] Endurecer tests de arquitectura.
- [ ] Actualizar SRS si algun nombre final cambio durante implementacion.

## Riesgos y codesmells restantes

- `ColorCatalog` puede volver a convertirse en verdad paralela.
- `TokenInventory` aun guarda metadata relacional que deberia ser derivada.
- `StyleCatalog` puede mezclar computed styles con authored CSS o usage derivable.
- `css_overview` sigue siendo dependencia fuerte para contraste.
- Strings de CSS properties pueden divergir de `CssPropertyId`.
- Payloads abundantes facilitan coerciones inconsistentes.
- `capture_prototype_structure` hace demasiadas cosas: canonicaliza, mergea colores, linkea overview y limpia runtime.
- `RenderArtifacts` introduce una fase paralela no reflejada por el SRS.
- `cluster_color_histogram` podria requerir optimizacion si se mide lentitud real en screenshots grandes.
