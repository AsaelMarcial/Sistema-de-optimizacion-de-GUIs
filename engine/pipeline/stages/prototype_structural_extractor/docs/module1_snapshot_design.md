# Módulo 1 — Prototype Structural Extraction

## 1) Estado actual del sistema y cómo se integra

Actualmente este stage se coordina desde `engine/pipeline/stages/prototype_structural_extractor`:

- `engine/pipeline/stages/prototype_structural_extractor/capture_original.py`: captura del prototipo original.
- `engine/pipeline/stages/prototype_structural_extractor/capture_transformed.py`: captura del prototipo transformado.

La lógica reutilizable vive en:

- `engine/services/prototype_structural_extractor/page_capture_service.py`: render del HTML y screenshot final.
- `engine/services/prototype_structural_extractor/render_snapshot_service.py`: snapshot, extracción y serialización.

Y la orquestación oficial vive en:

- `engine/pipeline/pipeline.py`

Con esta base, Módulo 1 es el stage canónico de captura y snapshot estructural (DOM+CSSOM+CDP). El artefacto externo actual sigue siendo `render_snapshot_original.json` por compatibilidad.

## 2) Validación de viabilidad y orden lógico

La estructura propuesta **sí es viable** con Playwright + CDP, y de hecho es el enfoque correcto para separar:

- Plano perceptual: estilos computados + geometría real del render.
- Plano declarativo: origen de reglas y especificidad mediante CDP.

Orden recomendado para reducir errores:

1. Cargar HTML con base path y esperar `load + networkidle + fonts.ready`.
2. Ejecutar barrido de DOM para recolectar estructura, geometría, estilos computados y estado visual (visible/no visible).
3. Abrir sesión CDP (`DOM.enable`, `CSS.enable`) y resolver `nodeId` por selector estable (`domPath`).
4. Consultar `CSS.getMatchedStylesForNode` para traza declarativa.
5. Consultar `CSS.getBackgroundColors` para fondo efectivo y consolidar cada nodo.
6. Activar `CSS.startRuleUsageTracking` / `CSS.stopRuleUsageTracking` para `RuleUsage`.
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

## 4) Estructura declarativa CDP agregada

Para trazabilidad por nodo se serializa:

- `declaredSources.cdpMatchedStyles.ruleMatches` (RuleMatch)
- `declaredSources.cdpMatchedStyles.ruleMatches[*].selectorList` (SelectorList)
- `declaredSources.cdpMatchedStyles.inheritedStyleEntries` (InheritedStyleEntry)
- `declaredSources.backgroundColors` y `effectiveBackground` (desde `CSS.getBackgroundColors`)
- `snapshot.ruleUsage` (RuleUsage global)

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
  - orquestación de cobertura y serialización
- `engine/pipeline/stages/prototype_structural_extractor/`
  - coordinación del stage para original y transformado
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
- Colores: `colorAid.js` (HCT), y opcional `material-color-utilities` como verificación cruzada
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
- En `cdpMatchedStyles` se filtran reglas sin match efectivo y, por defecto, se excluye origen `user-agent` para evitar ruido de defaults.
- `computedColors` se filtra para conservar solo propiedades con declaración real detectada en inline/attributes/matched/inherited (no el universo completo de valores por default).
