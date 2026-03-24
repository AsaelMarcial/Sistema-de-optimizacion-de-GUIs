from __future__ import annotations

import os
import shutil


def is_dir_empty(path: str) -> bool:
    try:
        return len(os.listdir(path)) == 0
    except Exception:
        return False


def safe_rmtree(path: str) -> None:
    try:
        shutil.rmtree(path)
    except Exception:
        pass


def safe_remove(path: str) -> None:
    try:
        os.remove(path)
    except Exception:
        pass


def remove_empty_dirs(path: str) -> None:
    try:
        for root, dirs, _ in os.walk(path, topdown=False):
            for dirname in dirs:
                dir_path = os.path.join(root, dirname)
                if is_dir_empty(dir_path):
                    safe_rmtree(dir_path)
    except Exception:
        pass
