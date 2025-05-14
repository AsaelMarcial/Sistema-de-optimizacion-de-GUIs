import os
import time
import shutil
from config import SESSION_EXPIRE_MINUTES

def clean_old_sessions():
    now = time.time()

    # Limpiar /data/input/session_*
    clean_dir("data/input", "session_", now)

    # Limpiar /static/corrected/session_*
    clean_dir("static/corrected", "", now)

def clean_dir(base_dir, prefix, now):
    if not os.path.exists(base_dir):
        return
    for folder in os.listdir(base_dir):
        path = os.path.join(base_dir, folder)
        if os.path.isdir(path) and folder.startswith(prefix):
            age_minutes = (now - os.path.getmtime(path)) / 60
            if age_minutes > SESSION_EXPIRE_MINUTES:
                try:
                    shutil.rmtree(path)
                except Exception:
                    pass
