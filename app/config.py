# config.py

import os

MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {'.html', '.zip'}
ALLOWED_ZIP_CONTENT = {'.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg'}
SESSION_EXPIRE_MINUTES = 60

INPUT_SESSIONS_DIR = os.getenv("GUI_OPT_INPUT_SESSIONS_DIR", os.path.join("data", "input"))
STATIC_CORRECTED_DIR = os.getenv(
    "GUI_OPT_STATIC_CORRECTED_DIR",
    os.path.join("static", "corrected"),
)
STATIC_CORRECTED_SUBDIR = os.getenv("GUI_OPT_STATIC_CORRECTED_SUBDIR", "corrected")
