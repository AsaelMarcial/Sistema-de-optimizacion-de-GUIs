from __future__ import annotations

import io
from pathlib import Path
import shutil
import time
import zipfile

from app.config import SESSION_EXPIRE_MINUTES


def read_file_storage_bytes(file) -> bytes:
    stream = getattr(file, "stream", None)
    if stream is not None:
        seekable = getattr(stream, "seekable", None)
        position = stream.tell() if callable(seekable) and seekable() else None
        payload = stream.read()
        if position is not None:
            stream.seek(position)
        return bytes(payload)

    payload = getattr(file, "_payload", None)
    if payload is not None:
        return bytes(payload)

    reader = getattr(file, "read", None)
    if callable(reader):
        return bytes(reader())

    raise ValueError("No se pudo leer el archivo de entrada.")


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
            _validate_zip_targets(archive, target_dir)
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


def read_text(path: str | Path) -> str:
    return Path(path).resolve().read_text(encoding="utf-8")


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
        session_id = path.name[len("session_"):]
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
            raise OSError(f"No se pudo reemplazar el ZIP existente: {final_zip_path}") from exc
    shutil.make_archive(str(bundle_base), "zip", source)
    return str(final_zip_path), final_zip_path.name


def _validate_zip_targets(archive: zipfile.ZipFile, destination: Path) -> None:
    for member in archive.infolist():
        target = (destination / member.filename).resolve()
        try:
            target.relative_to(destination)
        except ValueError as exc:
            raise ValueError(f"ZIP inseguro: {member.filename}") from exc


def _protected_session_ids(active_session_id: str | None) -> set[str]:
    value = str(active_session_id or "").strip()
    if not value:
        return set()
    if value.startswith("session_"):
        return {value, value[len("session_"):]}
    return {value, f"session_{value}"}
