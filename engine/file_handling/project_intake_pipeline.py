from __future__ import annotations

import os

from engine.file_handling.models import ProjectInput
from engine.file_handling.services.artifact_storage_service import read_text
from engine.file_handling.services.project_structure_service import (
    find_single_html_file,
    normalize_base_path_for_single_subdir,
)
from engine.file_handling.services.session_workspace_service import build_session_workspace
from engine.file_handling.services.upload_ingestion_service import ingest_uploaded_file


def process_project_upload(file, session_id: str) -> ProjectInput | str:
    result = ingest_uploaded_file(file, session_id)
    if isinstance(result, str):
        return result

    base_path, resolved_session_id, upload_path = result
    workspace = build_session_workspace(resolved_session_id)
    normalized_base_path = normalize_base_path_for_single_subdir(base_path)

    try:
        if upload_path.lower().endswith(".html"):
            html_path = upload_path
        else:
            html_path = find_single_html_file(normalized_base_path)
    except (FileNotFoundError, ValueError) as exc:
        return str(exc)

    html_filename = os.path.basename(html_path)

    try:
        html_content = read_text(html_path)
    except Exception:
        return "No se pudo leer el archivo HTML."

    return ProjectInput(
        session_id=resolved_session_id,
        workspace=workspace,
        upload_path=upload_path,
        base_path=base_path,
        normalized_base_path=normalized_base_path,
        html_path=html_path,
        html_filename=html_filename,
        html_content=html_content,
    )
