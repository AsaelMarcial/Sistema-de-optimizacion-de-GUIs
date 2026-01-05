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
6. Render GUI optimizada → píxeles → colores
7. Calcular energía/CO₂/SCI optimizada
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
