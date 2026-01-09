import os
import time
import shutil
from config import SESSION_EXPIRE_MINUTES


# archivos temporales que pueden quedar si hubo crash durante render
TEMP_RENDER_FILES = {"__glow_render__.html"}

def clean_old_sessions():
    """
    Limpia inputs temporales y outputs de sesiones.

    - /data/input/session_* : borra sesiones viejas
    - /static/corrected/<session_id>/ : borra sesiones viejas o vacías
    - /static/corrected/<session_id>.zip : borra zips viejos
    - Limpia archivos temporales __glow_render__.html dentro de carpetas de sesión
      (solo si la sesión ya expiró o si el directorio está vacío/colgado).
    """
    now = time.time()

    # 1) /data/input/session_*
    _clean_dirs(base_dir="data/input", prefix="session_", now=now)

    # 2) /static/corrected/<session_id> (carpetas)
    _clean_dirs(base_dir="static/corrected", prefix="", now=now)

    # 3) /static/corrected/<session_id>.zip
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

        # A) Si expiró -> borrar TODO
        if age_minutes > SESSION_EXPIRE_MINUTES:
            _safe_rmtree(path)
            continue

        # B) Si no expiró: limpieza ligera
        #    - borrar archivos temporales si existen (por si quedaron colgados)
        _remove_temp_files(path)

        #    - si está vacío y ya pasó 1 minuto -> borrar carpeta
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


def _remove_temp_files(dir_path: str) -> None:
    """
    Borra archivos temporales de render dentro de un dir (recursivo).
    Es seguro porque esos archivos no deben formar parte del resultado final.
    """
    try:
        for root, _, files in os.walk(dir_path):
            for f in files:
                if f in TEMP_RENDER_FILES:
                    _safe_remove(os.path.join(root, f))
    except Exception:
        pass


def _is_dir_empty(path: str) -> bool:
    try:
        return len(os.listdir(path)) == 0
    except Exception:
        return False


def _safe_rmtree(path: str) -> None:
    try:
        shutil.rmtree(path)
    except Exception:
        pass


def _safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except Exception:
        pass
