from __future__ import annotations

import os
import zipfile

from app.config import ALLOWED_ZIP_CONTENT


def is_safe_zip_member(member_name: str) -> bool:
    name = member_name.replace("\\", "/")

    if name.startswith("/") or (":" in name.split("/")[0]):
        return False

    parts = [part for part in name.split("/") if part not in ("", ".")]
    return not any(part == ".." for part in parts)


def validate_zip_members(zip_ref: zipfile.ZipFile) -> str | None:
    for member in zip_ref.infolist():
        if member.is_dir():
            continue

        if not is_safe_zip_member(member.filename):
            return f"ZIP inseguro: {member.filename}"

        ext = os.path.splitext(member.filename)[1].lower()
        if ext and ext not in ALLOWED_ZIP_CONTENT:
            return f"Archivo no permitido en ZIP: {member.filename}"

    return None
