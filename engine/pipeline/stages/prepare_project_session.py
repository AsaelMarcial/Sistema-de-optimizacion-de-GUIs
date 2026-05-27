from __future__ import annotations

from pathlib import Path

from engine.adapters.file_system.file_manager import (
    clean_old_sessions,
    extract_zip,
    read_file_storage_bytes,
    safe_rmtree,
    save_bytes,
    scan_files,
)
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.project_uploaded import (
    ALLOWED_INPUT_EXTENSIONS,
    ALLOWED_PROJECT_FILE_EXTENSIONS,
    exists,
    is_file_permitted,
    is_readable,
    is_safe_name,
    is_zip_readable,
)


def _prepared_session(session: Session) -> bool:
    try:
        if not session.get_area_root("before").is_dir() or not session.get_area_root("after").is_dir():
            return False
        if len(session.find_by_suffix("before", ("html",))) != 1:
            return False
        if len(session.find_by_suffix("after", ("html",))) != 1:
            return False
        return all(path.is_file() for path in session._before["paths"]) and all(
            path.is_file() for path in session._after["paths"]
        )
    except (FileNotFoundError, RuntimeError, ValueError, OSError):
        return False


CONTRACT = StageContract(
    name="prepare_project_session",
    requires=(),
    produces=(context_value(K.SESSION, Session, validator=_prepared_session),),
)


def run_stage(
    context: PipelineContext,
    upload,
) -> PipelineContext:
    if context.error:
        return context

    session: Session | None = None
    context.trace.add_stage_event(CONTRACT.name, "start")

    try:
        filename = getattr(upload, "filename", "")
        context.trace.add_step("input.received", {"filename": filename})

        if not exists(upload) or not exists(filename):
            raise ValueError("No se seleccionó ningún archivo.")

        input_filename = str(filename).strip()
        if not is_safe_name(input_filename):
            raise ValueError("Nombre de archivo no valido.")
        if not is_file_permitted(input_filename, ALLOWED_INPUT_EXTENSIONS):
            raise ValueError("Archivo no permitido")

        payload = read_file_storage_bytes(upload)
        extension = Path(input_filename).suffix.lower()
        context.trace.add_step(
            "input.basic_validated",
            {"filename": input_filename, "extension": extension, "bytes": len(payload)},
        )

        match extension:
            case ".html":
                if not is_readable(payload, text=True):
                    raise ValueError("No se pudo leer el archivo HTML.")
            case ".zip":
                if not is_zip_readable(payload):
                    raise ValueError("ZIP corrupto")
            case _:
                raise ValueError("Archivo no permitido")

        session = Session()
        clean_old_sessions(active_session_id=session.session_id, base_dir=session.session_dir.parent)

        match extension:
            case ".html":
                _materialize_html(payload, Path(input_filename).name, session)
                context.trace.add_step("project.materialized", {"kind": "html"})
            case ".zip":
                _materialize_zip(payload, session)
                context.trace.add_step("project.materialized", {"kind": "zip"})
            case _:
                raise ValueError("Archivo no permitido")

        _index_materialized_files(session)
        _validate_materialized_project(session)

        context.set(K.SESSION, session)
        context.trace.add_step(
            "session.workspace_materialized",
            {
                "session_id": session.session_id,
                "before_dir": str(session.get_area_root("before")),
                "after_dir": str(session.get_area_root("after")),
                "artifacts_dir": str(session.get_area_root("artifacts")),
            },
        )
        context.trace.add_stage_event(
            CONTRACT.name,
            "complete",
            {"session_id": session.session_id},
        )
        return context
    except Exception as exc:
        if session is not None and safe_rmtree(session.session_dir):
            context.trace.add_step("session.cleanup", {"session_dir": str(session.session_dir)})
        return _fail(context, str(exc))


def _materialize_html(payload: bytes, filename: str, session: Session) -> None:
    save_bytes(payload, session.get_area_root("before") / filename)
    save_bytes(payload, session.get_area_root("after") / filename)


def _materialize_zip(payload: bytes, session: Session) -> None:
    extract_zip(payload, session.get_area_root("before"))
    extract_zip(payload, session.get_area_root("after"))


def _index_materialized_files(session: Session) -> None:
    for path in scan_files(session.get_area_root("before")):
        session.save_in_before(path)
    for path in scan_files(session.get_area_root("after")):
        session.save_in_after(path)
    for path in scan_files(session.get_area_root("artifacts")):
        session.save_in_artifacts(path)


def _validate_materialized_project(session: Session) -> None:
    before_root = session.get_area_root("before")
    after_root = session.get_area_root("after")
    before_files = tuple(Path(path).resolve() for path in session._before["paths"])
    after_files = tuple(Path(path).resolve() for path in session._after["paths"])

    if not before_files:
        raise ValueError("El proyecto materializado no contiene archivos.")
    if not after_files:
        raise ValueError("El proyecto materializado no contiene archivos en after.")

    before_relative_paths = _relative_file_paths(before_files, before_root)
    after_relative_paths = _relative_file_paths(after_files, after_root)
    if before_relative_paths != after_relative_paths:
        missing_after = sorted(before_relative_paths - after_relative_paths)
        unexpected_after = sorted(after_relative_paths - before_relative_paths)
        details = []
        if missing_after:
            details.append(f"faltan en after: {', '.join(path.as_posix() for path in missing_after)}")
        if unexpected_after:
            details.append(f"sobran en after: {', '.join(path.as_posix() for path in unexpected_after)}")
        raise ValueError(f"before y after no tienen la misma estructura ({'; '.join(details)}).")

    for path in (*before_files, *after_files):
        if not is_file_permitted(path, ALLOWED_PROJECT_FILE_EXTENSIONS):
            root = before_root if path.is_relative_to(before_root) else after_root
            relative_path = path.relative_to(root)
            raise ValueError(f"Archivo no permitido en proyecto: {relative_path}")

    before_html_candidates = session.find_by_suffix("before", ("html",))
    after_html_candidates = session.find_by_suffix("after", ("html",))
    if len(before_html_candidates) != 1 or len(after_html_candidates) != 1:
        raise ValueError("El proyecto debe tener exactamente un archivo .html.")

    before_html = before_html_candidates[0]
    after_html = after_html_candidates[0]
    if before_html.relative_to(before_root) != after_html.relative_to(after_root):
        raise ValueError("El HTML principal de before y after no coincide.")

    if not is_readable(before_html.read_bytes(), text=True):
        raise ValueError(f"No se pudo leer el HTML: {before_html}")
    if not is_readable(after_html.read_bytes(), text=True):
        raise ValueError(f"No se pudo leer el HTML: {after_html}")


def _relative_file_paths(paths: tuple[Path, ...], root: Path) -> set[Path]:
    relative_paths: set[Path] = set()
    for path in paths:
        if not path.is_file():
            raise ValueError(f"Ruta indexada no es archivo: {path}")
        try:
            relative_paths.add(path.relative_to(root))
        except ValueError as exc:
            raise ValueError(f"Ruta fuera del area de sesion: {path}") from exc
    return relative_paths


def _fail(context: PipelineContext, message: str) -> PipelineContext:
    context.trace.add_step("input.error", {"message": message})
    context.trace.add_stage_event(CONTRACT.name, "error", {"message": message})
    return context.set_error(message)
