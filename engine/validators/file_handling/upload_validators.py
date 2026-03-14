from __future__ import annotations

import os

from app.config import ALLOWED_EXTENSIONS


def allowed_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


def validate_uploaded_file(file) -> str | None:
    if not file or not getattr(file, "filename", ""):
        return "No se seleccionó ningún archivo."

    if not allowed_file(file.filename):
        return "Archivo no permitido"

    return None
