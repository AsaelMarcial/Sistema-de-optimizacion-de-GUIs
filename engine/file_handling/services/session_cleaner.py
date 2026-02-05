import os
import time
import shutil

from app.config import SESSION_EXPIRE_MINUTES
from engine.file_handling.services.session_handler import (
    get_session_dir_prefix,
    get_sessions_base_dir,
    get_session_dirname_parts,
)


# archivos temporales que pueden quedar si hubo crash durante render
TEMP_RENDER_FILES = {"__glow_render__.html"}

def clean_old_sessions(active_session_id: str | None = None) -> None:
    """
    Limpia inputs temporales y outputs de sesiones.

    - /workspace/sessions/session_<id>/input : borra sesiones viejas
    - /workspace/sessions/session_<id>/output : borra sesiones viejas
    - /workspace/sessions/session_<id>/artifacts : borra sesiones viejas
    - Limpia archivos temporales __glow_render__.html dentro de carpetas de sesión
      (solo si la sesión ya expiró o si el directorio está vacío/colgado).
    """
    now = time.time()
    protected_session_ids = {active_session_id} if active_session_id else set()

    _clean_session_dirs(
        base_dir=get_sessions_base_dir(),
        prefix=get_session_dir_prefix(),
        now=now,
        protected_session_ids=protected_session_ids,
    )



def _clean_session_dirs(
    base_dir: str,
    prefix: str,
    now: float,
    protected_session_ids: set[str],
) -> None:
    if not os.path.exists(base_dir):
        return

    for name in os.listdir(base_dir):
        path = os.path.join(base_dir, name)

        if not os.path.isdir(path):
            continue

        if prefix and not name.startswith(prefix):
            continue

        session_id = name[len(prefix) :] if prefix else name
        if session_id in protected_session_ids:
            continue

        age_minutes = (now - os.path.getmtime(path)) / 60.0

        # A) Si expiró -> borrar TODO
        if age_minutes > SESSION_EXPIRE_MINUTES:
            _safe_rmtree(path)
            continue

        # B) Si no expiró: limpieza ligera
        #    - borrar archivos temporales si existen (por si quedaron colgados)
        for subdir in get_session_dirname_parts():
            subdir_path = os.path.join(path, subdir)
            if os.path.exists(subdir_path):
                _remove_temp_files(subdir_path)
                if _is_dir_empty(subdir_path) and age_minutes > 1:
                    _safe_rmtree(subdir_path)

        #    - si está vacío y ya pasó 1 minuto -> borrar carpeta
        if _is_dir_empty(path) and age_minutes > 1:
            _safe_rmtree(path)


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

