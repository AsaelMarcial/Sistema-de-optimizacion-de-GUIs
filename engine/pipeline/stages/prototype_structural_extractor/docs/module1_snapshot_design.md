# Módulo 1 — Prototype Structural Extraction

## 1) Estado actual del sistema y cómo se integra

Actualmente este stage se coordina desde `engine/pipeline/stages/prototype_structural_extractor/stage.py`.

La lógica reutilizable vive en:

- `engine/services/prototype_structural_extractor/page_capture_service.py`: render del HTML y screenshot final.
- `engine/services/prototype_structural_extractor/render_snapshot_service.py`: snapshot, extracción y serialización.
- `engine/services/prototype_structural_extractor/style_trace_service.py`: inventario global de estilos y resolución real de cascada por propiedad.
- `engine/services/prototype_structural_extractor/snapshot_normalization_service.py`: normalización final del contrato serializable.

Y la orquestación oficial vive en:

- `engine/pipeline/pipeline.py`

Con esta base, Módulo 1 es el stage canónico de captura y snapshot estructural (DOM+CSSOM+CDP). El artefacto externo actual sigue siendo `render_snapshot_original.json` por compatibilidad, pero su contrato ya usa inventarios explícitos de elementos y estilos.

## 2) Validación de viabilidad y orden lógico

La estructura propuesta **sí es viable** con Playwright + CDP, y de hecho es el enfoque correcto para separar:

- Plano perceptual: estilos computados + geometría real del render.
- Plano declarativo: origen de reglas y especificidad mediante CDP.

Orden recomendado para reducir errores:

1. Cargar HTML con base path y esperar `load + networkidle + fonts.ready`.
2. Ejecutar barrido de DOM para recolectar estructura, geometría, estilos computados y estado visual (visible/no visible).
3. Abrir sesión CDP (`DOM.enable`, `CSS.enable`) y resolver `nodeId` por selector estable (`domPath`).
4. Consultar `CSS.getMatchedStylesForNode` para traza declarativa por nodo.
5. Consultar `CSS.getBackgroundColors` para fondo efectivo y consolidar cada nodo.
6. Resolver la cascada real por propiedad computada usando:
   - `matchedCSSRules`
   - `inherited`
   - `matchingSelectors`
   - especificidad del selector matched
   - expansión de shorthand con `CSS.getLonghandProperties`
   - resolución contextual con `CSS.resolveValues`
7. Guardar JSON + metadatos de extracción (conteo, URL, viewport, timestamp).

## 3) Propiedades de color y caja capturadas en v1

Se incluyeron explícitamente las propiedades solicitadas:

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
- Geometría de cajas:
  - `boxes.margin`, `boxes.padding`, `boxes.borderWidth`
  - y box model de CDP vía `DOM.getBoxModel`

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

`elements_inventory` es el inventario de elementos retenidos por el snapshot. Cada elemento conserva identidad, layout, jerarquía, flags, texto, estilos de fondo y un mapa `computed_styles`.

Cada `computed_styles[property_name]` apunta al estilo ganador real de la cascada con este shape:

- `computed_value`
- `style_id`
- `declared_property`
- `kind`
- `inherited_from_element_id` cuando aplique

Si no existe atribución confiable, se serializa:

- `computed_value`
- `resolution_status: "unresolved"`

Este diseño mantiene separado:

- inventario global de estilos declarados
- inventario de elementos y propiedad computada -> estilo ganador

## 5) LayoutTreeSnapshot vs enfoque actual

**¿Conviene usar `LayoutTreeSnapshot`?**

- `DOMSnapshot.captureSnapshot` / LayoutTreeSnapshot es excelente para capturar layout masivo y rápido (árbol + estilos computados por lista blanca), útil para analytics de gran escala.
- Nuestro enfoque actual (DOM + CSS por nodo + `CSS.getMatchedStylesForNode` + `CSS.getBackgroundColors` + rule usage) prioriza trazabilidad fina de origen de reglas y fondo efectivo textual, que es clave para tus módulos de transformación/override.

Recomendación práctica:

- Mantener el enfoque actual como base canónica de Módulo 1.
- Evaluar LayoutTreeSnapshot como optimización opcional para páginas muy grandes (modo performance), sin perder el enriquecimiento CDP crítico.

## 6) Estructura modular de archivos

Propuesta aplicada:

- `engine/services/prototype_structural_extractor/render_snapshot_service.py`
  - lógica principal de extracción del snapshot
  - orquestación de captura y serialización
- `engine/services/prototype_structural_extractor/style_trace_service.py`
  - inventario global de estilos
  - candidatos de cascada
  - selección del estilo ganador por propiedad computada
- `engine/pipeline/stages/prototype_structural_extractor/`
  - coordinación del stage para original y transformado desde un único `stage.py`
- `engine/pipeline/stages/prototype_structural_extractor/docs/module1_snapshot_design.md`
  - justificación, decisiones y roadmap

Esto deja el módulo autocontenido para que Módulo 2 consuma únicamente el JSON.

## 7) Sobre `html_utils.py`

`engine/utils/html_utils.py` puede seguir existiendo como utilitario opcional, pero no captura estado renderizado ni origen real de estilos. No debe ser la base de decisiones de transformación.

## 8) Referencias Adobe Spectrum (token naming y diff)

No son reemplazo del snapshot extractor, pero sí pueden aportar en Módulos 3–5:

- `token-name-parser/output`: referencia para normalizar convenciones de naming de tokens.
- `spectrum-diff-core`: útil para comparar cambios de tokens (antes/después).
- `markdown-generator`: útil para reportes técnicos y evidencia de tesis.

## 9) Tecnologías recomendadas por capa

- Extracción/render: **Playwright + CDP**
- Validación JSON: `jsonschema` o `pydantic`
- Calidad de código: `ruff`, `black`, `mypy`
- CSS analysis/lint: `stylelint` + `postcss` (para correlación fuente/override)
- Colores: `ColorAide` / `coloraide` (HCT, distance, contrast, alpha helpers), y `material-color-utilities` como referencia de modelos tonales
- Reportes: `pandas`/`polars` para exportar comparación Antes/Después

## 10) Plan de acción sugerido

1. Cerrar schema v1 de snapshot y reglas de visibilidad.
2. Usar `render_snapshot_original.json` como entrada canónica de Módulo 2.
3. Crear fixtures HTML de prueba (casos con malas prácticas semánticas).
4. Validar salida contra golden files JSON.
5. Definir contrato de entrada para Módulo 2 (normalización + clusterización).

## 11) Filtros aplicados para reducir ruido

- Solo se incluyen nodos `HTML`, `BODY` y descendientes dentro de `body`.
- Se excluyen etiquetas de metadata/embedded-media/math/scripting/edits/web-components/deprecated (por ejemplo `META`, `LINK`, `SCRIPT`, `IMG`, `VIDEO`, `SVG`, `MATH`, `SLOT`, `TEMPLATE`, etc.).
- En el inventario de estilos se filtran declaraciones fuera de scope y, por defecto, se puede excluir origen `user-agent` para reducir ruido.
- La resolución de cascada solo atribuye una propiedad cuando encuentra una declaración real que produzca exactamente el valor computado final; si no, la propiedad queda `unresolved`.
