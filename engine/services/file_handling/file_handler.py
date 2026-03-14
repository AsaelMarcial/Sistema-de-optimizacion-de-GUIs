from __future__ import annotations

import os
import zipfile

from werkzeug.utils import secure_filename

from engine.models.file_handling.project_input import ProjectInput
from engine.services.file_handling.session_handler import (
    build_input_session_dir,
    build_session_workspace,
)
from engine.utils.file_utils import read_text
from engine.validators.file_handling.archive_validators import validate_zip_members
from engine.validators.file_handling.upload_validators import validate_uploaded_file


def ingest_uploaded_file(file, session_id: str) -> tuple[str, str, str] | str:
    validation_error = validate_uploaded_file(file)
    if validation_error:
        return validation_error

    extension = os.path.splitext(file.filename)[1].lower()
    base_path = build_input_session_dir(session_id)
    safe_name = secure_filename(file.filename)
    upload_path = os.path.join(base_path, safe_name)
    file.save(upload_path)

    if extension == ".html":
        return base_path, session_id, upload_path

    if extension == ".zip":
        try:
            with zipfile.ZipFile(upload_path, "r") as archive:
                validation_message = validate_zip_members(archive)
                if validation_message:
                    return validation_message
                archive.extractall(base_path)
        except zipfile.BadZipFile:
            return "ZIP corrupto"
        except Exception:
            return "No se pudo extraer el ZIP"

        return base_path, session_id, upload_path

    return "Archivo no permitido"


def normalize_project_base_path(base_path: str) -> str:
    if not base_path or not os.path.isdir(base_path):
        return base_path

    subdirectories = [
        dirname
        for dirname in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, dirname))
    ]
    if len(subdirectories) == 1:
        return os.path.join(base_path, subdirectories[0])

    return base_path


def find_project_html_file(base_path: str) -> str:
    html_files: list[str] = []
    for root, _, files in os.walk(base_path):
        for filename in files:
            if filename.lower().endswith(".html"):
                html_files.append(os.path.join(root, filename))

    if not html_files:
        raise FileNotFoundError("No se encontró ningún archivo .html en el proyecto subido.")

    if len(html_files) > 1:
        raise ValueError(
            f"Se encontraron múltiples archivos .html: {html_files}. El proyecto debe tener solo uno."
        )

    return html_files[0]


def load_project_input(file, session_id: str) -> ProjectInput | str:
    ingestion_result = ingest_uploaded_file(file, session_id)
    if isinstance(ingestion_result, str):
        return ingestion_result

    base_path, resolved_session_id, upload_path = ingestion_result
    workspace = build_session_workspace(resolved_session_id)
    normalized_base_path = normalize_project_base_path(base_path)

    try:
        html_path = upload_path if upload_path.lower().endswith(".html") else find_project_html_file(
            normalized_base_path
        )
    except (FileNotFoundError, ValueError) as exc:
        return str(exc)

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
        html_filename=os.path.basename(html_path),
        html_content=html_content,
    )
