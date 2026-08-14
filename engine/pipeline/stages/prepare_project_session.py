from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path

from werkzeug.datastructures import FileStorage

from engine.adapters.file_system.file_manager import (
    clean_old_sessions,
    detect_type,
    is_corrupted,
    is_path_dangerous,
    safe_rmtree,
)
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.domain.utils.FFmpeg import generate_thumbnail


def _prepared_session(session: Session) -> bool:
    try:
        before_files = session.update_area_root_paths("before")
        return (
            session.get_area_root("before").is_dir()
            and bool(before_files)
            and all(path in session.file_types for path in before_files)
            and len(session.get_by_type(".html")) == 1
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
    upload: list[FileStorage],
) -> PipelineContext:
    if context.error:
        return context

    session = Session()
    clean_old_sessions(active_session_id=session.session_id, base_dir=session.session_dir.parent)
    context.trace.add_stage_event(CONTRACT.name, "start")

    try:
        files = upload or []
        file_count = len(files)
        analyzed_files: list[tuple[FileStorage, Path, str]] = []
        context.trace.add_step(
            "input.received",
            {
                "file_count": file_count,
                "filenames": [str(file.filename or "") for file in files],
            },
        )

        match file_count:
            case 0:
                raise ValueError("No se seleccionó ningún archivo.")
            case 1:
                file = files[0]
                filename = str(files[0].filename or "").strip()
                if not filename:
                    raise ValueError("No se seleccionó ningún archivo.")
                normalized_path, detected_type = _analyze_file(file)
                if detected_type != ".html" and detected_type != ".zip":
                    raise ValueError("Operation aborted. It has to be one HTML file.")
                elif detected_type == ".zip":
                    try:
                        file.seek(0)
                        with zipfile.ZipFile(file.stream, "r") as archive:
                            for info in archive.infolist():
                                if is_path_dangerous(Path(info.filename).as_posix()):
                                    raise ValueError(f"Operation aborted. Unsafe ZIP path: {info.filename}")
                                if info.is_dir():
                                    continue

                                with archive.open(info, "r") as stream:
                                    file_bytes = stream.read()

                                internal_storage = FileStorage(
                                    stream=io.BytesIO(file_bytes),
                                    filename=info.filename,
                                )

                                internal_path, internal_type = _analyze_file(internal_storage)

                                if internal_type == ".zip":
                                    raise ValueError("Operation aborted. ZIP files inside ZIP files are not allowed.")
                                if internal_type == "video":
                                    internal_path = internal_path.with_suffix(".jpeg")
                                    internal_storage = FileStorage(
                                        stream=io.BytesIO(generate_thumbnail(file_bytes)),
                                        filename=internal_path.as_posix(),
                                    )
                                analyzed_files.append((internal_storage, internal_path, internal_type))

                                if sum(1 for _, _, file_type in analyzed_files if file_type == ".html") > 1:
                                    raise ValueError("Operation aborted. Multiple HTML files are not allowed.")

                            if sum(1 for _, _, file_type in analyzed_files if file_type == ".html") != 1:
                                raise ValueError("Operation aborted. It has to be one HTML file.")

                            for analyzed_file, file_path, _file_type in analyzed_files:
                                output_path = session.get_area_root("before") / file_path
                                output_path.parent.mkdir(parents=True, exist_ok=True)
                                analyzed_file.seek(0)
                                with output_path.open("wb") as target:
                                    shutil.copyfileobj(analyzed_file.stream, target)
                            project_kind = "zip"
                    except zipfile.BadZipFile as exc:
                        raise ValueError(f"Operation aborted. ZIP corrupto: {exc}") from exc
                elif detected_type == ".html":
                    output_path = session.get_area_root("before") / normalized_path
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    file.seek(0)
                    with output_path.open("wb") as target:
                        shutil.copyfileobj(file.stream, target)
                    analyzed_files.append((file, normalized_path, detected_type))
                    project_kind = "files"
            case count if count > 1:
                for file in files:
                    normalized_path, detected_type = _analyze_file(file)
                    if detected_type == "directory":
                        raise ValueError("Operation aborted. Uncompressed directories are not allowed.")
                    if detected_type == ".zip":
                        raise ValueError("Operation aborted. Mixing a ZIP file and loose files is forbidden.")
                    if detected_type == "video":
                        normalized_path = normalized_path.with_suffix(".jpeg")
                        file = FileStorage(
                            stream=io.BytesIO(generate_thumbnail(file.stream)),
                            filename=normalized_path.as_posix(),
                        )
                    if any(file_path.stem.lower() == normalized_path.stem.lower() and file_path.parent.as_posix().lower() == normalized_path.parent.as_posix().lower() and file_type == detected_type for _, file_path, file_type in analyzed_files):
                        raise ValueError(f"Operation aborted. Duplicate file detected in request: {normalized_path.as_posix()}")
                    analyzed_files.append((file, normalized_path, detected_type))

                if sum(1 for _, _, type in analyzed_files if type == ".html") != 1:
                    raise ValueError("Operation aborted. It has to be one HTML file.")
                project_kind = "files"

                for file, file_path, _file_type in analyzed_files:
                    output_path = session.get_area_root("before") / file_path
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    file.seek(0)
                    with output_path.open("wb") as target:
                        shutil.copyfileobj(file.stream, target)

                    project_kind = "files"

        context.trace.add_step(
            "input.basic_validated",
            {
                "file_count": len(analyzed_files),
                "files": [
                    {
                        "path": relative_path.as_posix(),
                        "extension": detected_type,
                    }
                    for _file, relative_path, detected_type in analyzed_files
                ],
            },
        )

        session.validate_materialized_project("before", analyzed_files)

        context.set(K.SESSION, session)
        context.trace.add_step("project.materialized", {"kind": project_kind})
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


def _fail(context: PipelineContext, message: str) -> PipelineContext:
    context.trace.add_step("input.error", {"message": message})
    context.trace.add_stage_event(CONTRACT.name, "error", {"message": message})
    return context.set_error(message)

def _analyze_file(file: FileStorage) -> tuple[Path, str]:
    if is_path_dangerous(file.filename):
        raise ValueError(f"Operation aborted. Unsafe filename: {file.filename}")

    normalized_path = Path(Path(file.filename).as_posix())
    detected_type = detect_type(file)
    if not detected_type:
        raise ValueError(f"Operation aborted. Unknown or unsupported file type: {file.filename}")

    corrupted, message = is_corrupted(file, detected_type)
    if corrupted:
        raise ValueError(f"Operation aborted. {file.filename}: {message}")

    return normalized_path, detected_type
