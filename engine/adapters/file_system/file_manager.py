from __future__ import annotations

from pathlib import Path
import io
import shutil
import time
import zipfile

from app.config import SESSION_EXPIRE_MINUTES
from engine.domain.models.session import FilePath, SESSIONS_BASE_DIR, Session

TEMP_RENDER_FILES = {"__glow_render__.html"}


def ensure_dirs(*paths: str | Path) -> None:
    for path in paths:
        Path(path).mkdir(parents=True, exist_ok=True)


def read_file_storage_bytes(file) -> bytes:
    stream = getattr(file, "stream", None)
    if stream is not None:
        try:
            position = stream.tell()
        except Exception:
            position = None
        payload = stream.read()
        try:
            stream.seek(position or 0)
        except Exception:
            pass
        return payload

    payload = getattr(file, "_payload", None)
    if payload is not None:
        return bytes(payload)

    raise ValueError("No se pudo leer el archivo subido.")


def save_bytes(payload: bytes, destination: str | Path) -> Path:
    path = Path(destination)
    ensure_parent_dir(path)
    path.write_bytes(payload)
    return path


def extract_zip(payload: bytes | str | Path, destination_dir: str | Path) -> None:
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            archive.extractall(destination)
        return
    with zipfile.ZipFile(payload, "r") as archive:
        archive.extractall(destination)


def collect_file_paths(root: str | Path) -> tuple[FilePath, ...]:
    base = Path(root).resolve()
    if not base.exists() or not base.is_dir():
        return ()

    file_paths: list[FilePath] = []
    for directory, dirnames, filenames in base.walk():
        for dirname in dirnames:
            file_paths.append(FilePath.from_physical(directory / dirname, relative_to=base))
        for filename in filenames:
            file_paths.append(FilePath.from_physical(directory / filename, relative_to=base))
    return tuple(file_paths)


def ensure_parent_dir(path: str | Path) -> None:
    parent = Path(path).parent
    if str(parent):
        parent.mkdir(parents=True, exist_ok=True)


def save_text(path: str | Path, content: str) -> None:
    ensure_parent_dir(path)
    Path(path).write_text(content, encoding="utf-8")


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def is_dir_empty(path: str | Path) -> bool:
    try:
        return not any(Path(path).iterdir())
    except Exception:
        return False


def safe_rmtree(path: str | Path) -> None:
    try:
        shutil.rmtree(path)
    except Exception:
        pass


def safe_remove(path: str | Path) -> None:
    try:
        Path(path).unlink()
    except Exception:
        pass


def clean_old_sessions(
    active_session_id: str | None = None,
    *,
    base_dir: str | Path = SESSIONS_BASE_DIR,
) -> None:
    now = time.time()
    protected_session_ids = _protected_session_ids(active_session_id)
    _clean_session_dirs(
        base_dir=base_dir,
        now=now,
        protected_session_ids=protected_session_ids,
    )


def _protected_session_ids(active_session_id: str | None) -> set[str]:
    value = str(active_session_id or "").strip()
    if not value:
        return set()
    if value.startswith(Session.SESSION_PREFIX):
        return {value, value[len(Session.SESSION_PREFIX):]}
    return {value, f"{Session.SESSION_PREFIX}{value}"}


def _clean_session_dirs(
    *,
    base_dir: str | Path,
    now: float,
    protected_session_ids: set[str],
) -> None:
    base = Path(base_dir)
    if not base.exists():
        return

    for path in base.iterdir():
        if not path.is_dir():
            continue
        if not path.name.startswith(Session.SESSION_PREFIX):
            continue

        session_id = path.name[len(Session.SESSION_PREFIX):]
        if session_id in protected_session_ids or path.name in protected_session_ids:
            continue

        age_minutes = (now - path.stat().st_mtime) / 60.0

        if age_minutes >= SESSION_EXPIRE_MINUTES:
            safe_rmtree(path)
            continue

        for subdir in ("before", "after", "artifacts"):
            subdir_path = path / subdir
            if subdir_path.exists():
                _remove_temp_files(subdir_path)


def _remove_temp_files(dir_path: str | Path) -> None:
    try:
        for path in Path(dir_path).rglob("*"):
            if path.is_file() and path.name in TEMP_RENDER_FILES:
                safe_remove(path)
    except Exception:
        pass


def create_output_bundle(
    source_dir: str | Path,
    bundle_dir: str | Path,
    bundle_name: str,
) -> tuple[str, str]:
    bundle_stem = Path(bundle_name).stem
    bundle_base = str(Path(bundle_dir) / bundle_stem)
    final_zip_path = f"{bundle_base}.zip"
    if Path(final_zip_path).exists():
        safe_remove(final_zip_path)
    shutil.make_archive(bundle_base, "zip", source_dir)
    return final_zip_path, Path(final_zip_path).name
