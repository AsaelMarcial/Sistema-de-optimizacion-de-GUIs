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
6. Guardar JSON + metadatos de extracción (conteo, URL, viewport, timestamp).

## 3) Ajustes al schema JSON (mínimos críticos)

Además de lo que definiste, agrega:

- `renderState.display`
- `renderState.visibility`
- `renderState.opacity`
- `renderState.pointerEvents`
- `layout` con `width/height=0` para filtrar nodos no renderizados
- `metadata.nodeCount`
- `metadata.basePath`
- `metadata.capturedAt`
- `viewport` y `documentSize`

Estas propiedades permiten filtrar nodos invisibles sin destruir trazabilidad.

## 4) Estructura modular de archivos (aislado de Módulos 2–4)

Propuesta aplicada:

- `engine/rendering/services/render_snapshot_extractor.py`
  - lógica principal de extracción del snapshot
  - helpers CDP y serialización
- `engine/rendering/services/snapshot_cli.py`
  - punto de entrada CLI para ejecutar solo Módulo 1
- `engine/rendering/docs/module1_snapshot_design.md`
  - justificación, decisiones y roadmap

Esto deja el módulo autocontenido para que Módulo 2 consuma únicamente el JSON.

## 5) Sobre `html_parser.py`

`engine/analysis/utils/html_parser.py` era útil como conteo preliminar por etiquetas, pero no captura estado renderizado ni origen real de estilos. Se recomienda dejarlo como utilitario opcional, no como base de decisiones de transformación.

## 6) Referencias Adobe Spectrum (token naming y diff)

No son reemplazo del snapshot extractor, pero sí pueden aportar en Módulos 3–5:

- `token-name-parser/output`: referencia para normalizar convenciones de naming de tokens.
- `spectrum-diff-core`: útil para comparar cambios de tokens (antes/después).
- `markdown-generator`: útil para reportes técnicos y evidencia de tesis.

## 7) Tecnologías recomendadas por capa

- Extracción/render: **Playwright + CDP**
- Validación JSON: `jsonschema` o `pydantic`
- Calidad de código: `ruff`, `black`, `mypy`
- CSS analysis/lint: `stylelint` + `postcss` (para correlación fuente/override)
- Colores: `colorAid.js` (HCT), y opcional `material-color-utilities` como verificación cruzada
- Reportes: `pandas`/`polars` para exportar comparación Antes/Después

## 8) Plan de acción sugerido

1. Cerrar schema v1 de snapshot y reglas de visibilidad.
2. Usar `render_snapshot_original.json` como entrada canónica de Módulo 2.
3. Crear fixtures HTML de prueba (casos con malas prácticas semánticas).
4. Validar salida contra golden files JSON.
5. Definir contrato de entrada para Módulo 2 (normalización + clusterización).
