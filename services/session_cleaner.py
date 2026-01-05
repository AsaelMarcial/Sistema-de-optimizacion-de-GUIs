import os
import time
import shutil
from config import SESSION_EXPIRE_MINUTES


def clean_old_sessions():
    """
    Limpia inputs temporales y outputs de sesiones.
    - Borra carpetas de sesión viejas (age > SESSION_EXPIRE_MINUTES)
    - Borra carpetas vacías (age > 1 min) para evitar acumulación
    - Borra ZIPs viejos en static/corrected
    """
    now = time.time()

    # /data/input/session_*
    _clean_dirs(base_dir="data/input", prefix="session_", now=now)

    # /static/corrected/<session_id> (carpetas)
    _clean_dirs(base_dir="static/corrected", prefix="", now=now)

    # /static/corrected/<session_id>.zip (archivos)
    _clean_zips(base_dir="static/corrected", now=now)


def _clean_dirs(base_dir: str, prefix: str, now: float) -> None:
    if not os.path.exists(base_dir):
        return

    for name in os.listdir(base_dir):
        path = os.path.join(base_dir, name)

        if not os.path.isdir(path):
            continue

        if prefix and not name.startswith(prefix):
            continue

        age_minutes = (now - os.path.getmtime(path)) / 60.0

        # 1) Borra directorios viejos
        if age_minutes > SESSION_EXPIRE_MINUTES:
            _safe_rmtree(path)
            continue

        # 2) Borra directorios vacíos “colgados”
        #    (deja 1 min de margen para no borrar carpetas en uso)
        if _is_dir_empty(path) and age_minutes > 1:
            _safe_rmtree(path)


def _clean_zips(base_dir: str, now: float) -> None:
    if not os.path.exists(base_dir):
        return

    for name in os.listdir(base_dir):
        path = os.path.join(base_dir, name)
        if os.path.isfile(path) and name.lower().endswith(".zip"):
            age_minutes = (now - os.path.getmtime(path)) / 60.0
            if age_minutes > SESSION_EXPIRE_MINUTES:
                _safe_remove(path)


def _is_dir_empty(path: str) -> bool:
    try:
        return len(os.listdir(path)) == 0
    except Exception:
        return False


def _safe_rmtree(path: str) -> None:
    try:
        shutil.rmtree(path)
    except Exception:
        # En refactor posterior, aquí podríamos registrar error si lo necesitas
        pass


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except Exception:
        pass
