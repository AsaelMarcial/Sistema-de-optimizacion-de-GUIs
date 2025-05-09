import os
import time
from config import SESSION_EXPIRE_MINUTES

def clean_old_sessions():
    base_dir = "data/input"
    if not os.path.exists(base_dir):
        return

    now = time.time()
    for folder in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, folder)
        if os.path.isdir(folder_path) and folder.startswith("session_"):
            mtime = os.path.getmtime(folder_path)
            age_minutes = (now - mtime) / 60
            if age_minutes > SESSION_EXPIRE_MINUTES:
                try:
                    import shutil
                    shutil.rmtree(folder_path)
                except Exception:
                    pass
