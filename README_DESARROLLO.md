# README de desarrollo

## Artefactos de ejecución

Para mantener el repositorio limpio, **no se deben commitear artefactos de ejecución de Python**.

Esto incluye, entre otros:

- Directorios `__pycache__/`
- Archivos `*.pyc`, `*.pyo`, `*.pyd`
- Archivos `*$py.class`

Estas rutas están cubiertas por `.gitignore` para evitar commits accidentales.

## Recomendación opcional en local

Si quieres reducir la generación de bytecode durante desarrollo local, puedes ejecutar la aplicación con:

```bash
PYTHONDONTWRITEBYTECODE=1
```

> Nota: esta configuración es opcional y está pensada solo para desarrollo.
