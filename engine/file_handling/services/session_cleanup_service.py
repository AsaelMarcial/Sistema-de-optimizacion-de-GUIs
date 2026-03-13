from __future__ import annotations

import os
import shutil
import time

from app.config import SESSION_EXPIRE_MINUTES
from engine.file_handling.services.session_workspace_service import (
    get_session_dir_prefix,
    get_session_dirname_parts,
    get_sessions_base_dir,
)

TEMP_RENDER_FILES = {"__glow_render__.html"}


def clean_old_sessions(active_session_id: str | None = None) -> None:
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

        session_id = name[len(prefix):] if prefix else name
        if session_id in protected_session_ids:
            continue

        age_minutes = (now - os.path.getmtime(path)) / 60.0

        if age_minutes > SESSION_EXPIRE_MINUTES:
            _safe_rmtree(path)
            continue

        for subdir in get_session_dirname_parts():
            subdir_path = os.path.join(path, subdir)
            if os.path.exists(subdir_path):
                _remove_temp_files(subdir_path)
                if _is_dir_empty(subdir_path) and age_minutes > 1:
                    _safe_rmtree(subdir_path)

        if age_minutes > 1:
            _remove_empty_dirs(path)
            if _is_dir_empty(path):
                _safe_rmtree(path)


def _remove_temp_files(dir_path: str) -> None:
    try:
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if filename in TEMP_RENDER_FILES:
                    _safe_remove(os.path.join(root, filename))
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


def _remove_empty_dirs(path: str) -> None:
    try:
        for root, dirs, _ in os.walk(path, topdown=False):
            for dirname in dirs:
                dir_path = os.path.join(root, dirname)
                if _is_dir_empty(dir_path):
                    _safe_rmtree(dir_path)
    except Exception:
        pass
