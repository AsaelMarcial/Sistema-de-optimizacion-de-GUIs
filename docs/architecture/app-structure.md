# Convención de estructura para rutas Flask

## Decisión vigente
El proyecto mantiene una estructura **mínima** con un solo blueprint principal (`main`).
Por esta razón, las rutas se consolidan en un único módulo:

- `app/routes.py`

## Regla de evolución
- Mientras exista un único blueprint, conservar `app/routes.py` como fuente de verdad.
- Si se agregan más blueprints (por ejemplo: `auth`, `admin`, `api`), migrar a paquete:
  - `app/routes/__init__.py`
  - `app/routes/<blueprint>_routes.py`

## Import recomendado en la app factory
Desde `app/__init__.py`, importar así para la convención actual:

```python
from app.routes import main
```

Esta convención evita refactors inversos (paquete ↔ archivo único) sin criterio explícito.
