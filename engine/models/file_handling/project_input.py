from __future__ import annotations

from dataclasses import dataclass

from engine.models.file_handling.session_workspace import SessionWorkspace


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
