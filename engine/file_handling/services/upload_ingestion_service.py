from __future__ import annotations

import os
import zipfile

from werkzeug.utils import secure_filename

from engine.file_handling.services.session_workspace_service import build_input_session_dir
from engine.file_handling.validators.archive_validators import validate_zip_members
from engine.file_handling.validators.upload_validators import validate_uploaded_file


def ingest_uploaded_file(file, session_id: str) -> tuple[str, str, str] | str:
    validation_error = validate_uploaded_file(file)
    if validation_error:
        return validation_error

    ext = os.path.splitext(file.filename)[1].lower()
    base_path = build_input_session_dir(session_id)

    safe_name = secure_filename(file.filename)
    upload_path = os.path.join(base_path, safe_name)
    file.save(upload_path)

    if ext == ".html":
        return base_path, session_id, upload_path

    if ext == ".zip":
        try:
            with zipfile.ZipFile(upload_path, "r") as zip_ref:
                error = validate_zip_members(zip_ref)
                if error:
                    return error
                zip_ref.extractall(base_path)
        except zipfile.BadZipFile:
            return "ZIP corrupto"
        except Exception:
            return "No se pudo extraer el ZIP"

        return base_path, session_id, upload_path

    return "Archivo no permitido"
