from __future__ import annotations

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
    get_session_dirname,
)
from engine.file_handling.models import SessionWorkspace


def generate_session_id() -> str:
    return str(uuid.uuid4())[:8]


def build_session_workspace(session_id: str) -> SessionWorkspace:
    session_dir = get_session_dir(session_id)
    input_dir = get_input_dir(session_id)
    output_dir = get_output_dir(session_id)
    artifacts_dir = get_artifacts_dir(session_id)

    os.makedirs(session_dir, exist_ok=True)
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(artifacts_dir, exist_ok=True)

    return SessionWorkspace(
        session_id=session_id,
        session_dir=session_dir,
        input_dir=input_dir,
        output_dir=output_dir,
        artifacts_dir=artifacts_dir,
        session_dirname=get_session_dirname(session_id),
    )


def build_input_session_dir(session_id: str) -> str:
    return build_session_workspace(session_id).input_dir


def prepare_static_session_dir(session_id: str) -> dict:
    workspace = build_session_workspace(session_id)
    return {
        "output_dir": workspace.output_dir,
        "artifacts_dir": workspace.artifacts_dir,
    }


def get_sessions_base_dir() -> str:
    return SESSIONS_BASE_DIR


def get_session_dir_prefix() -> str:
    return SESSION_DIR_PATTERN.format(session_id="")


def get_session_dirname_parts() -> tuple[str, str, str]:
    return INPUT_DIRNAME, OUTPUT_DIRNAME, ARTIFACTS_DIRNAME
