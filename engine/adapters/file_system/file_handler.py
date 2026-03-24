import os
import shutil
import time
import uuid
import zipfile

from werkzeug.utils import secure_filename

from app.config import (
    ARTIFACTS_DIRNAME,
    INPUT_DIRNAME,
    OUTPUT_DIRNAME,
    SESSION_EXPIRE_MINUTES,
    SESSIONS_BASE_DIR,
    SESSION_DIR_PATTERN,
    get_artifacts_dir,
    get_input_dir,
    get_output_dir,
    get_session_dir,
    get_session_dirname,
)
from engine.adapters.utils.filesystem import is_dir_empty, remove_empty_dirs, safe_remove, safe_rmtree
from engine.adapters.utils.io import read_text
from engine.domain.models.session import ProjectInputModel, SessionModel
from engine.validators.file_handling.archive_validators import validate_zip_members
from engine.validators.file_handling.upload_validators import validate_uploaded_file

TEMP_RENDER_FILES = {"__glow_render__.html"}

SessionWorkspace = SessionModel
ProjectInput = ProjectInputModel


def generate_session_id() -> str:
    return str(uuid.uuid4())[:8]


def build_session_workspace(session_id: str) -> SessionWorkspace:
    workspace = SessionWorkspace.build(
        session_id=session_id,
        session_dirname=get_session_dirname(session_id),
        base_dir=SESSIONS_BASE_DIR,
        input_dirname=INPUT_DIRNAME,
        output_dirname=OUTPUT_DIRNAME,
        artifacts_dirname=ARTIFACTS_DIRNAME,
    )
    workspace.ensure_exists()
    return workspace


def build_input_session_dir(session_id: str) -> str:
    return build_session_workspace(session_id).input_dir


def prepare_static_session_dir(session_id: str) -> dict[str, str]:
    workspace = build_session_workspace(session_id)
    return {
        "output_dir": workspace.output_dir,
        "artifacts_dir": workspace.artifacts_dir,
    }


def get_sessions_base_dir() -> str:
    return SESSIONS_BASE_DIR


def get_session_dir_prefix() -> str:
    return SESSION_DIR_PATTERN.format(session_id="")


def get_session_dirname_parts() -> tuple[str, str, str]:
    return INPUT_DIRNAME, OUTPUT_DIRNAME, ARTIFACTS_DIRNAME


def clean_old_sessions(active_session_id: str | None = None) -> None:
    now = time.time()
    protected_session_ids = {active_session_id} if active_session_id else set()
    _clean_session_dirs(
        base_dir=get_sessions_base_dir(),
        prefix=get_session_dir_prefix(),
        now=now,
        protected_session_ids=protected_session_ids,
    )


def _clean_session_dirs(
    base_dir: str,
    prefix: str,
    now: float,
    protected_session_ids: set[str],
) -> None:
    if not os.path.exists(base_dir):
        return

    for name in os.listdir(base_dir):
        path = os.path.join(base_dir, name)
        if not os.path.isdir(path):
            continue
        if prefix and not name.startswith(prefix):
            continue

        session_id = name[len(prefix):] if prefix else name
        if session_id in protected_session_ids:
            continue

        age_minutes = (now - os.path.getmtime(path)) / 60.0

        if age_minutes > SESSION_EXPIRE_MINUTES:
            safe_rmtree(path)
            continue

        for subdir in get_session_dirname_parts():
            subdir_path = os.path.join(path, subdir)
            if os.path.exists(subdir_path):
                _remove_temp_files(subdir_path)
                if is_dir_empty(subdir_path) and age_minutes > 1:
                    safe_rmtree(subdir_path)

        if age_minutes > 1:
            remove_empty_dirs(path)
            if is_dir_empty(path):
                safe_rmtree(path)


def _remove_temp_files(dir_path: str) -> None:
    try:
        for root, _, files in os.walk(dir_path):
            for filename in files:
                if filename in TEMP_RENDER_FILES:
                    safe_remove(os.path.join(root, filename))
    except Exception:
        pass


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
        raise FileNotFoundError("No se encontro ningun archivo .html en el proyecto subido.")

    if len(html_files) > 1:
        raise ValueError(
            f"Se encontraron multiples archivos .html: {html_files}. El proyecto debe tener solo uno."
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

    project_input = ProjectInput(
        session=workspace,
        upload_path=upload_path,
        base_path=base_path,
        normalized_base_path=normalized_base_path,
        html_path=html_path,
        html_filename=os.path.basename(html_path),
        html_content=html_content,
    )
    project_input.validate()
    return project_input


def create_output_bundle(
    source_dir: str,
    bundle_dir: str,
    bundle_name: str,
) -> tuple[str, str]:
    bundle_stem = os.path.splitext(bundle_name)[0]
    bundle_base = os.path.join(bundle_dir, bundle_stem)
    final_zip_path = f"{bundle_base}.zip"
    if os.path.exists(final_zip_path):
        safe_remove(final_zip_path)
    shutil.make_archive(bundle_base, "zip", source_dir)
    return final_zip_path, os.path.basename(final_zip_path)
