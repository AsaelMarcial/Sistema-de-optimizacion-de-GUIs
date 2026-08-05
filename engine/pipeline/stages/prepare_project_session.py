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


def _prepared_session(session: Session) -> bool:
    try:
        return session.get_area_root("before").is_dir() and session.validate_materialized_project("before")
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
        context.trace.add_step(
            "input.received",
            {
                "file_count": len(files),
                "filenames": [str(file.filename or "") for file in files],
            },
        )

        if not files:
            raise ValueError("No se seleccionó ningún archivo.")

        input_records: list[tuple[FileStorage, Path, str]] = []
        for file in files:
            filename = str(file.filename or "").strip()
            if not filename:
                raise ValueError("No se seleccionó ningún archivo.")

            relative_path = Path(filename.replace("\\", "/"))
            if is_path_dangerous(relative_path):
                raise ValueError(f"Operation aborted. Unsafe filename: {filename}")

            detected_type = detect_type(file)
            if not detected_type:
                raise ValueError(f"Operation aborted. Unknown or unsupported file type: {filename}")
            if detected_type == "directory":
                raise ValueError("Operation aborted. Uncompressed directories are not allowed.")

            corrupted, message = is_corrupted(file, detected_type)
            if corrupted:
                raise ValueError(f"Operation aborted. {filename}: {message}")

            input_records.append(
                (
                    file,
                    relative_path,
                    detected_type,
                )
            )

        input_types = [detected_type for _file, _path, detected_type in input_records]
        is_zip_mode = len(input_records) == 1 and input_types[0] == ".zip"

        if not is_zip_mode and ".zip" in input_types:
            raise ValueError("Operation aborted. Mixing a ZIP file and loose files is forbidden.")

        if not is_zip_mode and input_types.count(".html") != 1:
            raise ValueError("Operation aborted. It has to be one HTML file.")

        context.trace.add_step(
            "input.basic_validated",
            {
                "file_count": len(input_records),
                "files": [
                    {
                        "path": relative_path.as_posix(),
                        "extension": detected_type,
                    }
                    for _file, relative_path, detected_type in input_records
                ],
            },
        )

        if is_zip_mode:
            zip_storage = input_records[0][0]
            html_count = 0

            try:
                zip_storage.seek(0)
                with zipfile.ZipFile(zip_storage.stream, "r") as archive:
                    for info in archive.infolist():
                        internal_path = Path(info.filename.replace("\\", "/"))
                        if is_path_dangerous(internal_path):
                            raise ValueError(f"Operation aborted. Unsafe ZIP path: {info.filename}")
                        if info.is_dir():
                            continue

                        file_bytes = archive.read(info)
                        internal_storage = FileStorage(
                            stream=io.BytesIO(file_bytes),
                            filename=info.filename,
                        )
                        internal_type = detect_type(internal_storage)

                        if not internal_type:
                            raise ValueError(f"Operation aborted. Unsupported file inside ZIP: {info.filename}")
                        if internal_type == ".zip":
                            raise ValueError("Operation aborted. ZIP files inside ZIP files are not allowed.")

                        corrupted, message = is_corrupted(internal_storage, internal_type)
                        if corrupted:
                            raise ValueError(f"Operation aborted. {info.filename}: {message}")

                        if internal_type == ".html":
                            html_count += 1

                    if html_count != 1:
                        raise ValueError("Operation aborted. It has to be one HTML file.")
                    archive.extractall(session.get_area_root("before"))
            except zipfile.BadZipFile as exc:
                raise ValueError(f"Operation aborted. ZIP corrupto: {exc}") from exc

            project_kind = "zip"
        else:
            seen_paths: set[Path] = set()
            for _file, relative_path, _detected_type in input_records:
                if relative_path in seen_paths:
                    raise ValueError(f"Operation aborted. Duplicate file detected in request: {relative_path.as_posix()}")
                seen_paths.add(relative_path)

            for file, relative_path, _detected_type in input_records:
                output_path = session.get_area_root("before") / relative_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                file.seek(0)
                with output_path.open("wb") as target:
                    shutil.copyfileobj(file.stream, target)

            project_kind = "files"

        session.validate_materialized_project("before")

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
