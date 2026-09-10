from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path
from types import MappingProxyType

import magic
import PIL
from PIL import Image
from werkzeug.datastructures import FileStorage

from app.exceptions.GlowException import PipelineValidationError
from engine.adapters.file_system.file_manager import is_path_dangerous

EXTENSION_TO_TYPES = MappingProxyType(
    {
        ".html": {
            "text/html",
            "application/xhtml+xml",
            "text/plain",
        },
        ".htm": {
            "text/html",
            "application/xhtml+xml",
            "text/plain",
        },
        ".css": {
            "text/css",
            "text/plain",
        },
        ".js": {
            "text/javascript",
            "application/javascript",
            "text/plain",
        },
        ".txt": {
            "text/plain",
        },
        ".xml": {
            "application/xml",
            "text/xml",
        },
        ".png": {
            "image/png",
        },
        ".jpg": {
            "image/jpeg",
        },
        ".jpeg": {
            "image/jpeg",
        },
        ".svg": {
            "image/svg+xml",
            "image/svg",
            "application/xml",
            "text/xml",
            "text/plain",
        },
        ".webp": {
            "image/webp",
        },
        ".gif": {
            "image/gif",
        },
        ".ico": {
            "image/x-icon",
            "image/vnd.microsoft.icon",
        },
        ".bmp": {
            "image/bmp",
            "image/x-ms-bmp",
        },
        ".mp4": {
            "video/mp4",
        },
        ".m4v": {
            "video/x-m4v",
        },
        ".mov": {
            "video/quicktime",
        },
        ".webm": {
            "video/webm",
        },
        ".ogv": {
            "video/ogg",
        },
        ".zip": {
            "application/zip",
            "application/x-zip-compressed",
        },
    }
)

TEXT_EXTENSION_MIME_TYPES = MappingProxyType(
    {
        ".html": "text/html",
        ".htm": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".xml": "application/xml",
        ".svg": "image/svg+xml",
    }
)


def save_file(path_name: str | Path, content: bytes) -> Path:
    """
    Saves a new file to disk and returns the created path.
    """
    if not path_name:
        raise ValueError("path_name must be provided.")

    path = Path(path_name)
    if path.exists():
        raise FileExistsError(f"El archivo ya existe: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as target:
        target.write(content)

    return path


def copy_directory_tree(source_directory: str | Path, path_name: str | Path) -> Path:
    """
    Copies a directory tree to a new directory and returns the destination path.
    """
    source = Path(source_directory)
    destination = Path(path_name)

    if not source.is_dir():
        raise NotADirectoryError(f"El directorio origen no existe: {source}")
    if destination.exists():
        raise FileExistsError(f"El directorio destino ya existe: {destination}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    return Path(shutil.copytree(source, destination))


def modify_file(path_name: str | Path, content: bytes) -> Path:
    """
    Replaces an existing file content and returns the modified path.
    """
    path = Path(path_name)
    if not path.is_file():
        raise FileNotFoundError(f"El archivo no existe: {path}")

    with path.open("wb") as target:
        target.write(content)

    return path


def extract_all(
    zip_file: str | Path | bytes,
    path_name: str | Path,
    members: list[str],
) -> Path:
    """
    Extracts selected ZIP members into a directory and returns that directory.
    """

    if members:
        archive_source = (
            io.BytesIO(zip_file) if isinstance(zip_file, bytes) else zip_file
        )
        with zipfile.ZipFile(archive_source, "r") as archive:
            if set(members) <= set(archive.namelist()):
                Path(path_name).mkdir(parents=True, exist_ok=True)
                archive.extractall(Path(path_name), members=members)
                return Path(path_name)

    raise ValueError("No pudo extraer el archivo ZIP.")


def validate_image(content: bytes) -> None:
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()  # Verifies image structural integrity
    except (PIL.UnidentifiedImageError, OSError, SyntaxError) as e:
        raise PipelineValidationError("CORRUPTED_ASSET", str(e)) from e


def validate_text(content: bytes) -> None:
    try:
        content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as e:
        raise PipelineValidationError("CORRUPTED_ASSET", str(e)) from e


def validate_video(content: bytes) -> None:
    # Antes se validaba el video y se generaba un thumbnail JPEG para usarlo
    # como asset visual. Se deja fuera por ahora; se puede retomar con PyAV
    # o FFmpeg cuando el flujo vuelva a aceptar video.
    raise PipelineValidationError("INVALID_FILE_TYPE", None)


def file_validator(
    file_list: list[FileStorage],
) -> list[dict[str, str | bytes | Path]]:
    """
    Validates a batch of FileStorage objects using a error-controlled loop.
    Instantiates a single magic.Magic instance to optimize CPU usage.
    """
    detector = magic.Magic(mime=True)
    validated_files: list[dict[str, str | bytes | Path]] = []

    for file in file_list:
        if not file.stream or not file.filename:
            raise PipelineValidationError("MISSING_UPLOAD", file.filename)
        if is_path_dangerous(file.filename):
            raise PipelineValidationError("SECURITY_VIOLATION", file.filename)

        try:
            file.stream.seek(0)
            content = file.read()
            suffix = Path(file.filename).suffix.lower()
            real_mime = detector.from_buffer(content[:2048])
            if suffix == ".zip" and zipfile.is_zipfile(io.BytesIO(content)):
                real_mime = "application/zip"
            mime_type = (
                TEXT_EXTENSION_MIME_TYPES.get(suffix, real_mime)
                if real_mime in {"application/xml", "text/plain", "text/xml"}
                else real_mime
            )

            if (
                real_mime in {"application/zip", "application/x-zip-compressed"}
                and len(file_list) > 1
            ):
                raise PipelineValidationError("MULTIPLE_ZIP", file.filename)

            match real_mime:
                case (
                    "text/html"
                    | "application/xhtml+xml"
                    | "text/plain"
                    | "text/css"
                    | "text/javascript"
                    | "application/javascript"
                    | "text/xml"
                    | "application/xml"
                    | "image/svg+xml"
                    | "image/svg"
                ):
                    validate_text(content)
                    validated_files.append(
                        {
                            "file_name": Path(file.filename),
                            "content": content,
                            "mime_type": mime_type,
                        }
                    )

                case "application/zip" | "application/x-zip-compressed" if (
                    len(file_list) == 1
                ):
                    with zipfile.ZipFile(io.BytesIO(content), "r") as z:
                        corrupted_member = z.testzip()
                        if corrupted_member is not None:
                            raise PipelineValidationError(
                                "CORRUPTED_ASSET",
                                corrupted_member,
                            )

                        members = [info for info in z.infolist() if not info.is_dir()]
                        for info in members:
                            if (
                                is_path_dangerous(info.filename)
                                or Path(info.filename).suffix.lower() == ".zip"
                            ):
                                raise PipelineValidationError(
                                    "INTERNAL_ZIP_FILE",
                                    info.filename,
                                )

                        validated_files.extend(
                            file_validator(
                                [
                                    FileStorage(
                                        stream=io.BytesIO(z.read(info.filename)),
                                        filename=info.filename,
                                    )
                                    for info in members
                                ]
                            )
                        )

                case real_mime if real_mime.startswith("image/"):
                    validate_image(content)
                    validated_files.append(
                        {
                            "file_name": Path(file.filename),
                            "content": content,
                            "mime_type": mime_type,
                        }
                    )

                case real_mime if real_mime.startswith("video/"):
                    # Antes se validaba el video y se generaba un thumbnail JPEG.
                    # Lo dejamos fuera por ahora para retomarlo con PyAV/FFmpeg después.
                    raise PipelineValidationError("INVALID_FILE_TYPE", file.filename)
                case _ if suffix == ".css" or suffix == ".svg":
                    validated_files.append(
                        {
                            "file_name": Path(file.filename),
                            "content": content,
                            "mime_type": mime_type,
                        }
                    )

        except PipelineValidationError:
            raise
        except (magic.MagicException, zipfile.BadZipFile) as exc:
            raise PipelineValidationError("CORRUPTED_ASSET", str(exc)) from exc
        except Exception as exc:
            raise RuntimeError(
                f"unexpected error [{type(exc).__name__}]: {exc}"
            ) from exc

    return validated_files
