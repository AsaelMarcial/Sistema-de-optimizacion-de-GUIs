# Módulo 1 — Snapshot & Extraction (Render Snapshot Model)

## 1) Estado actual del sistema y cómo se integra

Actualmente ya existe un pipeline sólido en rendering:

- `engine/rendering/services/gui_rendering.py`: render del HTML y screenshot final.
- `engine/rendering/utils/pixel_frequency.py`: conteo y ordenamiento de píxeles por color.
- `engine/rendering/screenshot_analyzer.py`: une render + frecuencias de color.

Y en core:

- `engine/core/engine_pipeline.py` ejecuta el flujo principal.

Con esta base, Módulo 1 no debe reemplazar rendering, sino **complementarlo** con snapshot estructural (DOM+CSSOM+CDP). Por eso se integró como artefacto adicional (`render_snapshot_original.json`) dentro del pipeline.

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

## 6) Estructura modular de archivos (aislado de Módulos 2–4)

Propuesta aplicada:

- `engine/rendering/services/render_snapshot_extractor.py`
  - lógica principal de extracción del snapshot
  - helpers CDP y serialización
- `engine/rendering/services/snapshot_cli.py`
  - punto de entrada CLI para ejecutar solo Módulo 1
- `engine/rendering/docs/module1_snapshot_design.md`
  - justificación, decisiones y roadmap

Esto deja el módulo autocontenido para que Módulo 2 consuma únicamente el JSON.

## 7) Sobre `html_parser.py`

`engine/analysis/utils/html_parser.py` era útil como conteo preliminar por etiquetas, pero no captura estado renderizado ni origen real de estilos. Se recomienda dejarlo como utilitario opcional, no como base de decisiones de transformación.

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
