from __future__ import annotations

import io
from pathlib import Path
import shutil
import time
import zipfile
import re
from werkzeug.datastructures import FileStorage
from app.config import SESSION_EXPIRE_MINUTES
from PIL import Image
import magic

# Bidirectional mapping between MIME types and their standard official extensions
TYPE_TO_EXTENSION = {
    "text/html": ".html",
    "text/css": ".css",
    "text/javascript": ".js",
    "application/javascript": ".js",
    "text/plain": ".txt",
    "application/xml": ".xml",
    "text/xml": ".xml",
    "image/png": ".png",
    "image/jpeg": ".jpg",  # Cubre .jpg y .jpeg
    "image/svg+xml": ".svg",
    "image/svg": ".svg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "image/bmp": ".bmp",
    "image/x-ms-bmp": ".bmp",
    "video/mp4": ".mp4",
    "video/x-m4v": ".m4v",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
    "video/ogg": ".ogv",
    "application/zip": ".zip",
    "application/x-zip-compressed": ".zip",
}

DANGEROUS_PATTERN = re.compile(r'[\x00-\x1f\x7f\\/:*?"<>|;&$`]')

WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

ALLOWED_FILE_SUFFIXES = {
    ".html",
    ".css",
    ".js",
    ".txt",
    ".xml",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".webp",
    ".gif",
    ".ico",
    ".bmp",
    ".mp4",
    ".m4v",
    ".mov",
    ".webm",
    ".ogv",
    ".zip",
}

TEXT_FILE_SUFFIXES = {
    ".html",
    ".css",
    ".js",
    ".svg",
    ".txt",
    ".xml",
}


def is_path_dangerous(path: str | Path) -> bool:
    """
    Returns True if a relative path contains dangerous components.
    """
    if not path:
        return True
    path = Path(Path(path).as_posix())

    if path.is_absolute() or not path.parts or len(path.suffixes) > 1:
        return True

    for index, part in enumerate(path.parts):
        # Directorio padre, actual o vacío
        if part in ("", ".", ".."):
            return True

        # Espacios o puntos al inicio/final
        if part != part.strip(" ."):
            return True

        # Caracteres peligrosos
        if DANGEROUS_PATTERN.search(part):
            return True

        # Nombres reservados de Windows
        if Path(part).stem.upper() in WINDOWS_RESERVED_NAMES:
            return True

        # Último componente (archivo)
        if (
            index == len(path.parts) - 1
            and path.suffix
            and path.suffix.lower() not in ALLOWED_FILE_SUFFIXES
        ):
            return True

    return False


def detect_type(file: FileStorage) -> str:
    """Uses python.magic to detect the real type of the file."""
    if not file.stream or not file.filename:
        return ""

    file.seek(0)
    safe_block = file.read(64 * 1024)
    file.seek(0)  # Reset pointer position

    detected_mime = magic.from_buffer(safe_block, mime=True)
    file_suffix = Path(file.filename).suffix.lower()

    if file_suffix in TEXT_FILE_SUFFIXES and _is_text_mime_or_utf8(
        detected_mime,
        safe_block,
    ):
        return file_suffix

    match detected_mime:
        case mime if mime.startswith("video"):
            detected_type = "video"
        case "image/jpeg":
            detected_type = ".jpeg" if not file_suffix else file_suffix
        case _:
            detected_type = TYPE_TO_EXTENSION.get(detected_mime, "")

    return detected_type


def _is_text_mime_or_utf8(detected_mime: str, payload: bytes) -> bool:
    if detected_mime.startswith("text/") or detected_mime in {
        "application/javascript",
        "application/xml",
        "image/svg+xml",
        "image/svg",
        "text/xml",
    }:
        return True

    try:
        payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return False

    return True


def is_corrupted(file: FileStorage, detected_type: str) -> tuple[bool, str | None]:
    """
    Analiza la integridad estructural interna de TODO el archivo en memoria.
    Retorna True si el archivo está dañado, vacío o corrupto.
    """

    if not file.stream or not file.filename:
        return True, f"Target object is not a valid file: {file.filename}"

    try:
        file.seek(0)

        match detected_type:
            case ".png" | ".jpg" | ".jpeg" | ".webp" | ".gif" | ".ico" | ".bmp":
                with Image.open(file.stream) as img:
                    img.verify()
                return False, None

            case ".html" | ".css" | ".js" | ".svg" | ".txt" | ".xml":
                contenido = file.read().decode("utf-8", errors="strict")
                file.seek(0)  # Restaurar puntero tras leer texto
                if not contenido.strip():
                    return True, "Is an empty file"
                return False, None

            case ".zip":
                if not zipfile.is_zipfile(file.stream):
                    return True, "Is not a valid zip file"
                file.seek(0)
                with zipfile.ZipFile(file.stream) as zf:
                    if zf.testzip() is not None:
                        return True, "Is not a valid zip file"
                return False, None

            case "directory":
                return False, None

            case "video":
                # Video thumbnail/validation is disabled in the current upload flow.
                # Previously this delegated to FFmpeg/PyAV-style validation before
                # generating a JPEG thumbnail.
                from engine.domain.utils.FFmpeg import validate_video

                payload = file.read()
                file.seek(0)
                if validate_video(payload):
                    return True, "Video file is corrupted or unreadable."
                return False, None

            case _:
                return True, f"File type not allowed: {detected_type}"

    except Exception as exc:
        exception_type = type(exc).__name__
        return (
            True,
            f"Operation failed due to an unexpected error [{exception_type}]: {exc}",
        )
    finally:
        try:
            file.seek(0)
        except Exception:
            pass


def save_bytes(payload: bytes, destination: str | Path) -> Path:
    path = Path(destination).resolve()
    ensure_parent_dir(path)
    path.write_bytes(payload)
    return path


def extract_zip(payload: bytes, destination: str | Path) -> None:
    target_dir = Path(destination).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            archive.extractall(target_dir)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"El archivo ZIP está corrupto: {exc}") from exc


def scan_files(root: str | Path) -> tuple[Path, ...]:
    base = Path(root).resolve()
    if not base.is_dir():
        return ()
    return tuple(path.resolve() for path in base.rglob("*") if path.is_file())


def ensure_parent_dir(path: str | Path) -> None:
    Path(path).resolve().parent.mkdir(parents=True, exist_ok=True)


def safe_rmtree(path: str | Path) -> bool:
    target = Path(path).resolve()
    if not target.exists():
        return True
    try:
        shutil.rmtree(target)
        return True
    except OSError:
        return False


def clean_old_sessions(
    active_session_id: str | None = None,
    *,
    base_dir: str | Path,
    expire_minutes: int = SESSION_EXPIRE_MINUTES,
) -> int:
    base = Path(base_dir).resolve()
    if not base.is_dir():
        return 0

    now = time.time()
    protected_session_ids = _protected_session_ids(active_session_id)
    deleted_count = 0
    for path in base.iterdir():
        if not path.is_dir() or not path.name.startswith("session_"):
            continue
        session_id = path.name[len("session_") :]
        if session_id in protected_session_ids or path.name in protected_session_ids:
            continue
        age_minutes = (now - path.stat().st_mtime) / 60.0
        if age_minutes >= expire_minutes:
            if safe_rmtree(path):
                deleted_count += 1
    return deleted_count


def create_output_bundle(
    source_dir: str | Path,
    bundle_dir: str | Path,
    bundle_name: str,
) -> tuple[str, str]:
    source = Path(source_dir).resolve()
    target_dir = Path(bundle_dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    bundle_base = target_dir / Path(bundle_name).stem
    final_zip_path = bundle_base.with_suffix(".zip")
    if final_zip_path.exists():
        try:
            final_zip_path.unlink()
        except OSError as exc:
            raise OSError(
                f"No se pudo reemplazar el ZIP existente: {final_zip_path}"
            ) from exc
    shutil.make_archive(str(bundle_base), "zip", source)
    return str(final_zip_path), final_zip_path.name


def _protected_session_ids(active_session_id: str | None) -> set[str]:
    value = str(active_session_id or "").strip()
    if not value:
        return set()
    if value.startswith("session_"):
        return {value, value[len("session_") :]}
    return {value, f"session_{value}"}
