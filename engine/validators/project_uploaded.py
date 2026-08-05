from __future__ import annotations

import io
from pathlib import Path
import zipfile

ALLOWED_EXTENSIONS = {
    ".html",
    ".css",
    ".js",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".webp",
    ".zip",
}
ALLOWED_INPUT_EXTENSIONS = set(ALLOWED_EXTENSIONS)
ALLOWED_PROJECT_FILE_EXTENSIONS = set(ALLOWED_EXTENSIONS)

_INVALID_FILENAME_CHARS = set('<>:"/\\|?*')
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def exists(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, bytes, tuple, list, set, dict)):
        return bool(value)
    return True


def is_safe_name(name: str) -> bool:
    value = str(name or "").strip()
    if not value or value in {".", ".."}:
        return False
    if any(char in _INVALID_FILENAME_CHARS for char in value):
        return False
    if any(ord(char) < 32 for char in value):
        return False

    path = Path(value)
    if path.is_absolute() or len(path.parts) != 1 or ".." in path.parts:
        return False
    return path.stem.upper() not in _WINDOWS_RESERVED_NAMES


def is_safe_relative_path(path: str | Path) -> bool:
    candidate = Path(path)
    if not candidate.parts or candidate.is_absolute() or ".." in candidate.parts:
        return False
    return all(part not in {"", "."} and is_safe_name(part) for part in candidate.parts)


def is_file_permitted(path: str | Path, allowed_suffixes: set[str]) -> bool:
    suffix = Path(path).suffix.lower()
    return bool(suffix) and suffix in allowed_suffixes


def is_readable(payload: bytes, *, text: bool = False) -> bool:
    if not isinstance(payload, bytes):
        return False
    try:
        if text:
            payload.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def is_zip_readable(payload: bytes) -> bool:
    if not isinstance(payload, bytes):
        return False
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            return archive.testzip() is None
    except zipfile.BadZipFile:
        return False
