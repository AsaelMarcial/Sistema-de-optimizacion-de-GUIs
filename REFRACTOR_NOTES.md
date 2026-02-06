# GLOW - Refactor Notes

## Objetivo inmediato
Refactorizar módulo por módulo sin perder la versión funcional, manteniendo el output actual de `results.html`.

## Reglas (acuerdos)
- Mantener el flujo actual funcional en todo momento.
- No cambiar el contrato `results` que consume `templates/results.html`.
- Debug temporal solo en UI por ahora (bloque `<details>`).
- Se prueba siempre con el mismo ZIP de referencia (por ahora).

## Baseline
- Rama baseline: (anotar aquí el commit hash)
- Archivo principal de orquestación: `routes/main_routes.py`
- Carga de archivos: `services/file_handler.py`
- Limpieza de sesiones: `services/session_cleaner.py`

## Flujo actual (alto nivel)
1. Upload y extracción (ZIP/HTML)
2. Detectar HTML único
3. Render GUI original → píxeles → colores
4. Calcular energía/CO₂/SCI (1h, 1 usuario)
5. Aplicar heurísticas + copiar recursos + zip
6. Render GUI sustainable → píxeles → colores
7. Calcular energía/CO₂/SCI sustainable
8. Mostrar results + preview iframe + download ZIP

## Refactor plan (orden)
1) Main routes como orquestador (Refactor 1) ✅
2) File handler (seguridad + base_path consistente)
3) Gui analyzer (render/screenshot + paths)
4) Heuristic evaluator (separar: evaluar vs corregir vs métricas)
5) Energy/calculators (limpiar contrato y unidades)

## Notas / Issues detectados
- `handle_uploaded_file()` retorna `base_path=None` cuando se sube `.html`. El flujo espera `base_path` para resolver recursos. Se dejó un guard en routes con mensaje claro.
- `static/corrected` y `data/input` son runtime outputs: NO versionar en Git (agregar a .gitignore).


# GLOW - Refactor Notes

## Objetivo
Refactorizar por módulos sin romper el flujo funcional. Mantener el contrato de datos que consume `templates/results.html`.

## Reglas / acuerdos vigentes
- Siempre conservar una versión ejecutable (baseline) antes de cambios grandes.
- Mantener el dict `results` que se pasa a `results.html` (no romper keys/estructura).
- Debug temporal: se muestra en UI con `<details>` al final de results (colapsado). Se elimina al final.
- Pruebas manuales: subir siempre el mismo ZIP de referencia (por ahora).

## Baseline / commits recomendados
- Antes de cambios fuertes: correr el ZIP de prueba y hacer commit.
- Después de completar un refactor: correr el ZIP de prueba y hacer commit.

## Refactor 1 — main_routes como orquestador + DebugTrace (UI)
**Qué se hizo**
- Reestructuración de `routes/main_routes.py` para separar pasos y añadir trazas.
- Se agregó `utils/debug_logger.py` (`DebugTrace`) para recolectar pasos y exponerlos en `results["debug"]`.
- Se agregó panel `<details>` en `templates/results.html` para ver `results.debug` en JSON.
**Contrato**
- No se modificaron keys existentes en `results`; solo se añadió `results["debug"]`.

## Refactor 2 — services/file_handler robusto
**Qué se hizo**
- `services/file_handler.py` se hizo más robusto:
  - validación de extensiones
  - prevención de Zip Slip y rutas inseguras
  - lectura de HTML dentro del ZIP
  - `base_path` consistente (evitar None)
**Motivación**
- `base_path` es crítico para render correcto (recursos relativos CSS/images).

## Refactor 3 — extraer helpers fuera de main_routes
**Qué se hizo**
- Se movieron responsabilidades fuera de `routes/main_routes.py`:
  - `services/project_assets.py`:
    - `normalize_base_path_for_single_subdir`
    - `detectar_html_unico`
    - `copiar_recursos`
  - `utils/sci_rating.py`:
    - `compute_rating_from_sci`
  - `utils/gui_pipeline.py`:
    - `analyze_gui_to_color_data` (render -> pixels -> colors)
**Resultado**
- `main_routes.py` queda como orquestador y llama funciones de módulos.
- Se mantiene el contrato `results` para UI.

## Observaciones / Issues detectados
- Outputs runtime: `static/corrected/`, `data/input/`, `data/output/` no deben versionarse en git.
- `services/session_cleaner.py` debe eliminar carpetas vacías y ZIPs viejos en `static/corrected/` (pendiente si no se aplicó).
- Próximo refactor fuerte: `utils/gui_analyzer.py` (render). Problemas típicos: viewport, scrollbars, tamaño real, carga de recursos.

## Próximos pasos
- Refactor Render: migrar/ajustar `gui_analyzer` para usar Playwright con captura `full_page`, sin scrollbars, headless y viewport adaptable.
- Verificar dependencias y setup (Playwright + browsers) en equipo nuevo.
