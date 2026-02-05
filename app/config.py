# config.py

import os

MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {'.html', '.zip'}
ALLOWED_ZIP_CONTENT = {'.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg'}
SESSION_EXPIRE_MINUTES = 60

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(APP_ROOT, os.pardir))
STATIC_DIR = os.path.join(APP_ROOT, "static")

SESSIONS_BASE_DIR = os.getenv(
    "GUI_OPT_SESSIONS_DIR",
    os.path.join(PROJECT_ROOT, "workspace", "sessions"),
)
SESSION_DIR_PREFIX = "session_"
SESSION_DIR_PATTERN = f"{SESSION_DIR_PREFIX}{{session_id}}"
INPUT_DIRNAME = "input"
OUTPUT_DIRNAME = "output"
ARTIFACTS_DIRNAME = "artifacts"


def get_session_dirname(session_id: str) -> str:
    if session_id.startswith(SESSION_DIR_PREFIX):
        return session_id
    return SESSION_DIR_PATTERN.format(session_id=session_id)


def get_session_dir(session_id: str) -> str:
    return os.path.join(SESSIONS_BASE_DIR, get_session_dirname(session_id))


def get_input_dir(session_id: str) -> str:
    return os.path.join(get_session_dir(session_id), INPUT_DIRNAME)


def get_output_dir(session_id: str) -> str:
    return os.path.join(get_session_dir(session_id), OUTPUT_DIRNAME)


def get_artifacts_dir(session_id: str) -> str:
    return os.path.join(get_session_dir(session_id), ARTIFACTS_DIRNAME)

