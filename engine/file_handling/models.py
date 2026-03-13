from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionWorkspace:
    session_id: str
    session_dir: str
    input_dir: str
    output_dir: str
    artifacts_dir: str
    session_dirname: str


@dataclass(frozen=True, slots=True)
class ProjectInput:
    session_id: str
    workspace: SessionWorkspace
    upload_path: str
    base_path: str
    normalized_base_path: str
    html_path: str
    html_filename: str
    html_content: str
