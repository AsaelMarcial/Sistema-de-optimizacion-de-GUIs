from __future__ import annotations

import io
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import zipfile

ALLOWED_INPUT_EXTENSIONS = {".html", ".zip"}
ALLOWED_PROJECT_FILE_EXTENSIONS = {".html", ".css", ".js", ".png", ".jpg", ".jpeg", ".svg"}
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
    if value != os.path.basename(value):
        return False

    windows_path = PureWindowsPath(value)
    if windows_path.drive or windows_path.root or len(windows_path.parts) != 1:
        return False
    if Path(value).name != value:
        return False

    reserved_name = value.split(".", 1)[0].upper()
    return reserved_name not in _WINDOWS_RESERVED_NAMES


def is_safe_relative_path(path: str | PurePosixPath) -> bool:
    value = str(path or "").replace("\\", "/")
    if not value or value.startswith("/") or ":" in value.split("/")[0]:
        return False
    parts = PurePosixPath(value).parts
    return bool(parts) and all(part not in {"", ".", ".."} and is_safe_name(part) for part in parts)


def is_file_permitted(path: str | Path | PurePosixPath, allowed_suffixes: set[str]) -> bool:
    suffix = PurePosixPath(str(path).replace("\\", "/")).suffix.lower()
    return bool(suffix) and suffix in allowed_suffixes


def is_readable(source, *, text: bool = False) -> bool:
    try:
        if isinstance(source, bytes):
            payload = source
        elif isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists() or not path.is_file():
                return False
            if text:
                with path.open("r", encoding="utf-8") as file:
                    file.read()
            else:
                with path.open("rb") as file:
                    file.read(1)
            return True
        else:
            reader = getattr(source, "read", None)
            if not callable(reader):
                return False
            position = _tell(source)
            payload = reader(1 if not text else -1)
            _seek(source, position)

        if text:
            if isinstance(payload, str):
                payload.encode("utf-8").decode("utf-8")
            else:
                bytes(payload).decode("utf-8")
        return True
    except Exception:
        return False


def is_zip_readable(payload: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            return archive.testzip() is None
    except Exception:
        return False


def has_single_html(file_paths) -> bool:
    return len(html_files(file_paths)) == 1


def html_files(file_paths) -> tuple:
    return tuple(
        path
        for path in file_paths
        if getattr(path, "kind", "") == "file" and getattr(path, "suffix", "") == ".html"
    )


def single_html_file(file_paths):
    candidates = html_files(file_paths)
    if len(candidates) != 1:
        raise ValueError("El proyecto debe tener exactamente un archivo .html.")
    return candidates[0]


def _tell(source) -> int | None:
    try:
        return source.tell()
    except Exception:
        return None


def _seek(source, position: int | None) -> None:
    if position is None:
        return
    try:
        source.seek(position)
    except Exception:
        pass
