from __future__ import annotations

from pathlib import Path, PurePosixPath
import io
import zipfile

from engine.adapters.file_system.file_manager import (
    clean_old_sessions,
    collect_file_paths,
    extract_zip,
    read_file_storage_bytes,
    read_text,
    save_bytes,
)
from engine.domain.models.session import FilePath, SESSIONS_BASE_DIR, Session
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.project_uploaded import (
    ALLOWED_PROJECT_FILE_EXTENSIONS,
    ALLOWED_INPUT_EXTENSIONS,
    exists,
    has_single_html,
    is_file_permitted,
    is_readable,
    is_safe_name,
    is_safe_relative_path,
    is_zip_readable,
    single_html_file,
)


def _prepared_session(session: Session) -> bool:
    try:
        if not session.session_id.strip() or not session.file_paths:
            return False

        html_file = single_html_file(session.file_paths)
        before_root = session.build_path("before")
        after_root = session.build_path("after")
        if not before_root.is_dir() or not after_root.is_dir():
            return False

        for file_path in session.file_paths:
            before_path = session.build_path("before", file_path)
            after_path = session.build_path("after", file_path)
            if file_path.kind == "directory":
                if not before_path.is_dir() or not after_path.is_dir():
                    return False
                continue
            if not before_path.is_file() or not after_path.is_file():
                return False

        read_text(session.build_path("before", html_file))
        read_text(session.build_path("after", html_file))
        return True
    except Exception:
        return False


CONTRACT = StageContract(
    name="prepare_project_session",
    requires=(),
    produces=(context_value(K.SESSION, Session, validator=_prepared_session),),
)


def run_stage(context: PipelineContext, upload=None, *, base_dir=SESSIONS_BASE_DIR) -> PipelineContext:
    if context.error:
        return context

    context.trace.add_stage_event(CONTRACT.name, "start")
    filename = getattr(upload, "filename", "")
    context.trace.add_step("input.received", {"filename": filename})

    if not exists(upload) or not exists(filename):
        return _fail(context, "No se seleccionó ningún archivo.")

    input_filename = str(filename).strip()
    if not is_safe_name(input_filename):
        return _fail(context, "Nombre de archivo no valido.")

    if not is_file_permitted(input_filename, ALLOWED_INPUT_EXTENSIONS):
        return _fail(context, "Archivo no permitido")

    try:
        payload = read_file_storage_bytes(upload)
    except Exception:
        return _fail(context, "No se pudo leer el archivo subido.")
    context.trace.add_step("input.read", {"bytes": len(payload)})

    extension = Path(input_filename).suffix.lower()
    context.trace.add_step("input.basic_validated", {"filename": input_filename, "extension": extension})

    match extension:
        case ".html":
            if not is_readable(payload, text=True):
                return _fail(context, "No se pudo leer el archivo HTML.")

            session = Session(base_dir=base_dir, file_paths=(FilePath(input_filename),))
            context.trace.add_step("input.validated", {"kind": "html"})
            clean_old_sessions(active_session_id=session.session_id, base_dir=base_dir)

            html_file = single_html_file(session.file_paths)
            save_bytes(payload, session.build_path("before", html_file))
            save_bytes(payload, session.build_path("after", html_file))
            session.set_file_paths(collect_file_paths(session.build_path("before")))
            context.trace.add_step("project.materialized", {"kind": "html"})

        case ".zip":
            file_paths, error = _validate_zip_file_paths(
                input_filename=input_filename,
                payload=payload,
            )
            if error:
                return _fail(context, error)

            session = Session(base_dir=base_dir, file_paths=file_paths)
            context.trace.add_step("input.validated", {"kind": "zip"})
            clean_old_sessions(active_session_id=session.session_id, base_dir=base_dir)

            extract_zip(payload, session.build_path("before"))
            extract_zip(payload, session.build_path("after"))
            session.set_file_paths(collect_file_paths(session.build_path("before")))
            if not has_single_html(session.file_paths):
                return _fail(context, "El proyecto materializado debe tener exactamente un archivo .html.")
            context.trace.add_step(
                "project.materialized",
                {"kind": "zip", "root": session.project_root_file_path().name},
            )

        case _:
            return _fail(context, "Archivo no permitido")

    context.trace.add_step(
        "session.workspace_materialized",
        {
            "session_id": session.session_id,
            "before_dir": str(session.build_path("before")),
            "after_dir": str(session.build_path("after")),
        },
    )

    html_file = single_html_file(session.file_paths)
    try:
        read_text(session.build_path("before", html_file))
        read_text(session.build_path("after", html_file))
    except Exception as exc:
        return _fail(context, str(exc))

    context.set(K.SESSION, session)
    context.trace.add_step("input.handled", {"base_path": str(session.build_path("before", session.project_root_file_path()))})
    context.trace.add_step(
        "project.html_detected",
        {
            "html_path": str(session.build_path("before", html_file)),
            "html_name": html_file.name,
        },
    )
    context.trace.add_step(
        "session.created",
        {
            "session_id": session.session_id,
            "after_dir": str(session.build_path("after")),
            "artifacts_dir": str(session.build_path("artifacts")),
            "session_dirname": session.build_path("artifacts").parent.name,
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {"session_id": session.session_id, "html_name": html_file.name},
    )
    return context


def _validate_zip_file_paths(*, input_filename: str, payload: bytes) -> tuple[tuple[FilePath, ...], str | None]:
    if not is_zip_readable(payload):
        return (), "ZIP corrupto"

    file_paths: list[FilePath] = []
    try:
        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            for member in archive.infolist():
                member_path = PurePosixPath(member.filename.replace("\\", "/"))
                if not is_safe_relative_path(member_path):
                    return (), f"ZIP inseguro: {member.filename}"

                if member.is_dir():
                    file_paths.append(FilePath.from_zip_member(member_path, is_dir=True))
                    continue

                if not is_file_permitted(member_path, ALLOWED_PROJECT_FILE_EXTENSIONS):
                    return (), f"Archivo no permitido en ZIP: {member.filename}"
                try:
                    payload_member = archive.read(member)
                except Exception:
                    return (), f"No se pudo leer el archivo en ZIP: {member.filename}"
                if member_path.suffix.lower() == ".html" and not is_readable(payload_member, text=True):
                    return (), f"No se pudo leer el archivo en ZIP: {member.filename}"

                file_paths.extend(_parent_dirs_for_member(member_path))
                file_paths.append(FilePath.from_zip_member(member_path, is_dir=False))
    except zipfile.BadZipFile:
        return (), "ZIP corrupto"
    except Exception:
        return (), "No se pudo leer el ZIP."

    if not has_single_html(file_paths):
        return (), "El proyecto debe tener exactamente un archivo .html."

    return tuple(file_paths), None


def _parent_dirs_for_member(member_path: PurePosixPath) -> tuple[FilePath, ...]:
    dirs: list[FilePath] = []
    parts = member_path.parts[:-1]
    for index in range(1, len(parts) + 1):
        dirs.append(FilePath(Path(*parts[:index]), "directory"))
    return tuple(dirs)


def _fail(context: PipelineContext, message: str) -> PipelineContext:
    context.trace.add_step("input.error", {"message": message})
    context.trace.add_stage_event(CONTRACT.name, "error", {"message": message})
    return context.set_error(message)
