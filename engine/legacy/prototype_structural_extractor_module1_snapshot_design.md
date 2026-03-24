TODO: preserve for compatibility; refactor into proper layer later

# Modulo 1 - Prototype Structural Extraction

## 1) Estado actual del sistema y como se integra

Actualmente este stage se coordina desde `engine/pipeline/stages/prototype_structural_extractor/stage.py`.

La logica reutilizable vive en:

- `engine/services/prototype_structural_extractor/page_capture_service.py`: render del HTML y screenshot final.
- `engine/services/prototype_structural_extractor/render_snapshot_service.py`: snapshot, extraccion y serializacion.
- `engine/services/prototype_structural_extractor/style_trace_service.py`: inventario global de estilos y resolucion real de cascada por propiedad.
- `engine/services/prototype_structural_extractor/snapshot_normalization_service.py`: normalizacion final del contrato serializable.

Y la orquestacion oficial vive en:

- `engine/pipeline/pipeline.py`

Con esta base, Modulo 1 es el stage canonico de captura y snapshot estructural (DOM+CSSOM+CDP). El artefacto externo actual sigue siendo `render_snapshot_original.json` por compatibilidad, pero su contrato ya usa inventarios explicitos de elementos y estilos.

## 2) Validacion de viabilidad y orden logico

La estructura propuesta **si es viable** con Playwright + CDP, y de hecho es el enfoque correcto para separar:

- Plano perceptual: estilos computados + geometria real del render.
- Plano declarativo: origen de reglas y especificidad mediante CDP.

Orden recomendado para reducir errores:

1. Cargar HTML con base path y esperar `load + networkidle + fonts.ready`.
2. Ejecutar barrido de DOM para recolectar estructura, geometria, estilos computados y estado visual (visible/no visible).
3. Abrir sesion CDP (`DOM.enable`, `CSS.enable`) y resolver `nodeId` por selector estable (`domPath`).
4. Consultar `CSS.getMatchedStylesForNode` para traza declarativa por nodo.
5. Consultar `CSS.getBackgroundColors` para fondo efectivo y consolidar cada nodo.
6. Resolver la cascada real por propiedad computada usando:
   - `matchedCSSRules`
   - `inherited`
   - `matchingSelectors`
   - especificidad del selector matched
   - expansion de shorthand con `CSS.getLonghandProperties`
   - resolucion contextual con `CSS.resolveValues`
7. Guardar JSON + metadatos de extraccion (conteo, URL, viewport, timestamp).

## 3) Propiedades de color y caja capturadas en v1

Se incluyeron explicitamente las propiedades solicitadas:

- Texto/foreground:
  - `color` y `currentColor`
  - `textShadow`
  - `textDecorationColor`
  - `textEmphasisColor`
  - `caretColor`
- Fondos y cajas:
  - `backgroundColor`
  - `boxShadow`
  - `columnRuleColor`
  - `outlineColor`
- Bordes:
  - `borderColor` (shorthand)
  - `borderLeftColor`, `borderRightColor`, `borderTopColor`, `borderBottomColor`
  - `borderBlockStartColor`, `borderBlockEndColor`, `borderInlineStartColor`
- Geometria de cajas:
  - `boxes.margin`, `boxes.padding`, `boxes.borderWidth`
  - y box model de CDP via `DOM.getBoxModel`

## 4) Contrato del snapshot actual

El snapshot serializa:

- `metadata`
- `document`
- `elements_inventory`
- `styles_inventory`
- `palette`

`styles_inventory` es el inventario global deduplicado de estilos declarados relevantes en scope. Cada entrada conserva:

- `style_id`
- `kind`
- `origin`
- `style_sheet_id`
- `selector_text`
- `declarations`
- `matching_selector_index`
- `specificity`
- `source_range`
- `layer_name`
- `layer_order`
- `source_url`
- `node_ids`
- `usage_count`

`elements_inventory` es el inventario de elementos retenidos por el snapshot. Cada elemento conserva identidad, layout, jerarquia, flags, texto, estilos de fondo y un mapa `computed_styles`.

Cada `computed_styles[property_name]` apunta al estilo ganador real de la cascada con este shape:

- `computed_value`
- `style_id`
- `declared_property`
- `kind`
- `inherited_from_element_id` cuando aplique

Si no existe atribucion confiable, se serializa:

- `computed_value`
- `resolution_status: "unresolved"`

Este diseno mantiene separado:

- inventario global de estilos declarados
- inventario de elementos y propiedad computada -> estilo ganador

## 5) LayoutTreeSnapshot vs enfoque actual

**¿Conviene usar `LayoutTreeSnapshot`?**

- `DOMSnapshot.captureSnapshot` / LayoutTreeSnapshot es excelente para capturar layout masivo y rapido (arbol + estilos computados por lista blanca), util para analytics de gran escala.
- Nuestro enfoque actual (DOM + CSS por nodo + `CSS.getMatchedStylesForNode` + `CSS.getBackgroundColors` + rule usage) prioriza trazabilidad fina de origen de reglas y fondo efectivo textual, que es clave para tus modulos de transformacion/override.

Recomendacion practica:

- Mantener el enfoque actual como base canonica de Modulo 1.
- Evaluar LayoutTreeSnapshot como optimizacion opcional para paginas muy grandes (modo performance), sin perder el enriquecimiento CDP critico.

## 6) Estructura modular de archivos

Propuesta aplicada:

- `engine/services/prototype_structural_extractor/render_snapshot_service.py`
  - logica principal de extraccion del snapshot
  - orquestacion de captura y serializacion
- `engine/services/prototype_structural_extractor/style_trace_service.py`
  - inventario global de estilos
  - candidatos de cascada
  - seleccion del estilo ganador por propiedad computada
- `engine/pipeline/stages/prototype_structural_extractor/`
  - coordinacion del stage para original y transformado desde un unico `stage.py`
- `engine/pipeline/stages/prototype_structural_extractor/docs/module1_snapshot_design.md`
  - justificacion, decisiones y roadmap

Esto deja el modulo autocontenido para que Modulo 2 consuma unicamente el JSON.

## 7) Sobre `html_utils.py`

`engine/utils/html_utils.py` puede seguir existiendo como utilitario opcional, pero no captura estado renderizado ni origen real de estilos. No debe ser la base de decisiones de transformacion.

## 8) Referencias Adobe Spectrum (token naming y diff)

No son reemplazo del snapshot extractor, pero si pueden aportar en Modulos 3-5:

- `token-name-parser/output`: referencia para normalizar convenciones de naming de tokens.
- `spectrum-diff-core`: util para comparar cambios de tokens (antes/despues).
- `markdown-generator`: util para reportes tecnicos y evidencia de tesis.

## 9) Tecnologias recomendadas por capa

- Extraccion/render: **Playwright + CDP**
- Validacion JSON: `jsonschema` o `pydantic`
- Calidad de codigo: `ruff`, `black`, `mypy`
- CSS analysis/lint: `stylelint` + `postcss` (para correlacion fuente/override)
- Colores: `ColorAide` / `coloraide` (HCT, distance, contrast, alpha helpers), y `material-color-utilities` como referencia de modelos tonales
- Reportes: `pandas`/`polars` para exportar comparacion Antes/Despues

## 10) Plan de accion sugerido

1. Cerrar schema v1 de snapshot y reglas de visibilidad.
2. Usar `render_snapshot_original.json` como entrada canonica de Modulo 2.
3. Crear fixtures HTML de prueba (casos con malas practicas semanticas).
4. Validar salida contra golden files JSON.
5. Definir contrato de entrada para Modulo 2 (normalizacion + clusterizacion).

## 11) Filtros aplicados para reducir ruido

- Solo se incluyen nodos `HTML`, `BODY` y descendientes dentro de `body`.
- Se excluyen etiquetas de metadata/embedded-media/math/scripting/edits/web-components/deprecated (por ejemplo `META`, `LINK`, `SCRIPT`, `IMG`, `VIDEO`, `SVG`, `MATH`, `SLOT`, `TEMPLATE`, etc.).
- En el inventario de estilos se filtran declaraciones fuera de scope y, por defecto, se puede excluir origen `user-agent` para reducir ruido.
- La resolucion de cascada solo atribuye una propiedad cuando encuentra una declaracion real que produzca exactamente el valor computado final; si no, la propiedad queda `unresolved`.
