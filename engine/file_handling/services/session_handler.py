import os
import uuid

from app.config import (
    ARTIFACTS_DIRNAME,
    INPUT_DIRNAME,
    OUTPUT_DIRNAME,
    SESSIONS_BASE_DIR,
    SESSION_DIR_PATTERN,
    get_artifacts_dir,
    get_input_dir,
    get_output_dir,
    get_session_dir,
)


def generate_session_id() -> str:
    return str(uuid.uuid4())[:8]


def build_input_session_dir(session_id: str) -> str:
    session_dir = get_session_dir(session_id)
    input_dir = get_input_dir(session_id)
    os.makedirs(session_dir, exist_ok=True)
    os.makedirs(input_dir, exist_ok=True)
    return input_dir

def prepare_static_session_dir(session_id: str) -> dict:
    output_dir = get_output_dir(session_id)
    artifacts_dir = get_artifacts_dir(session_id)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(artifacts_dir, exist_ok=True)
    return {"output_dir": output_dir, "artifacts_dir": artifacts_dir}


def get_sessions_base_dir() -> str:
    return SESSIONS_BASE_DIR


def get_session_dir_prefix() -> str:
    return SESSION_DIR_PATTERN.format(session_id="")


def get_session_dirname_parts() -> tuple[str, str, str]:
    return INPUT_DIRNAME, OUTPUT_DIRNAME, ARTIFACTS_DIRNAME
