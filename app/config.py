# config.py

import os

MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {'.html', '.zip'}
ALLOWED_ZIP_CONTENT = {'.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg'}
SESSION_EXPIRE_MINUTES = 60

SESSIONS_BASE_DIR = os.getenv("GUI_OPT_SESSIONS_DIR", os.path.join("workspace", "sessions"))
SESSION_DIR_PATTERN = "session_{session_id}"
INPUT_DIRNAME = "input"
OUTPUT_DIRNAME = "output"
ARTIFACTS_DIRNAME = "artifacts"


def get_session_dir(session_id: str) -> str:
    return os.path.join(SESSIONS_BASE_DIR, SESSION_DIR_PATTERN.format(session_id=session_id))


def get_input_dir(session_id: str) -> str:
    return os.path.join(get_session_dir(session_id), INPUT_DIRNAME)


def get_output_dir(session_id: str) -> str:
    return os.path.join(get_session_dir(session_id), OUTPUT_DIRNAME)


def get_artifacts_dir(session_id: str) -> str:
    return os.path.join(get_session_dir(session_id), ARTIFACTS_DIRNAME)


STATIC_CORRECTED_DIR = os.getenv(
    "GUI_OPT_STATIC_CORRECTED_DIR",
    os.path.join("static", "corrected"),
)
STATIC_CORRECTED_SUBDIR = os.getenv("GUI_OPT_STATIC_CORRECTED_SUBDIR", "corrected")
