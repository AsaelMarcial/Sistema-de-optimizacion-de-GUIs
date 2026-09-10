from __future__ import annotations

from collections import Counter
from pathlib import Path

from flask import g
from prefect.states import Completed, State, raise_state_exception
from werkzeug.datastructures import FileStorage

from app.exceptions.GlowException import PipelineValidationError
from engine.adapters.file_system.file_manager import clean_old_sessions
from engine.domain.models.project_context import ProjectContext
from engine.pipeline.glow_runtime import glow_flow, glow_task
from engine.utilities.files import file_validator, save_file


@glow_task
def input_validation(
    file_list: list[FileStorage],
) -> list[dict[str, str | bytes | Path]]:
    if not file_list:
        raise PipelineValidationError("MISSING_UPLOAD", None)

    validated_files = file_validator(file_list)

    type_counter = Counter(str(file["mime_type"]) for file in validated_files)
    html_count = sum(
        1
        for file in validated_files
        if str(file["mime_type"]) in {"text/html", "application/xhtml+xml"}
        or Path(file["file_name"]).suffix.lower() in {".html", ".htm"}
    )
    if html_count == 0:
        raise PipelineValidationError("MISSING_HTML", None)
    if html_count > 1:
        raise PipelineValidationError("MULTIPLE_HTML", None)

    name_counter = Counter(Path(file["file_name"]) for file in validated_files)

    if (
        type_counter.get("application/zip", 0) > 1
        or type_counter.get("application/x-zip-compressed", 0) > 1
        or (
            type_counter.get("application/x-zip-compressed", 0) != 0
            and len(validated_files) > 1
        )
        or (type_counter.get("application/zip", 0) != 0 and len(validated_files) > 1)
    ):
        raise PipelineValidationError("MULTIPLE_ZIP", None)

    if any(name_counter[file] for file in name_counter if name_counter[file] > 1):
        print(
            f"DEBUG: Duplicate file names detected: {[file for file in name_counter if name_counter[file] > 1]}"
        )
        raise PipelineValidationError("INVALID_FILE_TYPE", None)

    return validated_files


@glow_task
def materialize_project_files(
    validated_files: list[dict[str, str | bytes | Path]],
) -> list[dict[str, str | Path]]:
    materialized_files: list[dict[str, str | Path]] = []

    g.before_root.mkdir(parents=True, exist_ok=True)
    g.artifacts_root.mkdir(parents=True, exist_ok=True)

    for file_info in validated_files:
        file_name = Path(file_info["file_name"])
        content = file_info["content"]
        mime_type = str(file_info["mime_type"])
        if not isinstance(content, bytes):
            raise PipelineValidationError("CORRUPTED_ASSET", file_name)

        saved_path = save_file(g.before_root / file_name, content)
        if not saved_path.exists():
            raise PipelineValidationError("CORRUPTED_ASSET", file_name)

        materialized_files.append(
            {
                "file_name": file_name,
                "mime_type": mime_type,
            }
        )

    return materialized_files


@glow_task
def _project_context_ready(project_context: ProjectContext | None) -> State:
    if (
        project_context is not None
        and project_context.session_dir.is_dir()
        and project_context.html is not None
        and project_context.html.absolute_path.is_file()
    ):
        return Completed(message="ProjectContext esta listo.")
    raise RuntimeError("ProjectContext no quedo preparado.")


@glow_flow
def prepare_project_session() -> None:
    try:
        upload = getattr(g, "upload", [])
        print(
            {
                "input.received": {
                    "file_count": len(upload),
                    "filenames": [str(file.filename or "") for file in upload],
                }
            }
        )
        if not upload:
            raise PipelineValidationError("MISSING_UPLOAD", None)

        validated_files = input_validation(upload)

        if not validated_files:
            raise PipelineValidationError("MISSING_UPLOAD", None)
        materialized_project = materialize_project_files(validated_files)
        if len(materialized_project) != len(validated_files):
            raise PipelineValidationError("CORRUPTED_ASSET", None)
        project_context = ProjectContext(
            materialized_project,
        )

        g.project_context = project_context

        print(
            {
                "project.materialized": {
                    "session_id": project_context.session_id,
                    "session_dir": g.session_dir,
                    "file_count": len(project_context),
                    "html_path": project_context.html.path.as_posix(),
                }
            }
        )

    except PipelineValidationError:
        raise
    except Exception as exc:
        raise RuntimeError(f"unexpected error [{type(exc).__name__}]: {exc}") from exc

    project_context_ready = _project_context_ready(
        project_context,
        return_state=True,
    )
    if (
        project_context_ready.is_failed()
        or project_context_ready.is_crashed()
        or project_context_ready.is_cancelled()
    ):
        raise_state_exception(project_context_ready)
