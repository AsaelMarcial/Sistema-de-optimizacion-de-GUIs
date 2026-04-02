from __future__ import annotations

from engine.adapters.file_system.file_handler import clean_old_sessions, generate_session_id, load_project_input
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _prepared_session(session: Session) -> bool:
    return (
        bool(session.session_id.strip())
        and bool(session.input_base_path.strip())
        and bool(session.input_html_path.strip())
        and bool(session.input_html_content.strip())
    )

CONTRACT = StageContract(
    name="prepare_project_session",
    requires=(
        context_value("session.input.file", allow_none=True),
    ),
    produces=(
        context_value("session", Session, validator=_prepared_session),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    context.trace.add_stage_event(CONTRACT.name, "start")
    session_id = generate_session_id()
    clean_old_sessions(active_session_id=session_id)

    upload = context.get("session.input.file")
    if upload is None:
        context.trace.add_stage_event(CONTRACT.name, "error", {"message": "missing_input_file"})
        return context.set_error("No se seleccionó ningún archivo.")

    context.trace.add_step("upload.received", {"filename": getattr(upload, "filename", None)})
    session = load_project_input(upload, session_id)
    if isinstance(session, str):
        context.trace.add_step("upload.error", {"message": session})
        context.trace.add_stage_event(CONTRACT.name, "error", {"message": session})
        return context.set_error(session)

    base_path = session.input_base_path
    if not base_path:
        context.trace.add_step("upload.missing_base_path", {})
        context.trace.add_stage_event(CONTRACT.name, "error", {"message": "missing_base_path"})
        return context.set_error(
            "Para análisis completo (CSS/imagenes), sube un ZIP con el HTML y sus recursos."
        )

    context.set("session", session)

    context.trace.add_step("upload.handled", {"base_path": base_path})
    context.trace.add_step(
        "project.html_detected",
        {
            "html_path": session.input_html_path,
            "html_name": session.input_html_name,
        },
    )
    context.trace.add_step(
        "session.created",
        {
            "session_id": session_id,
            "output_dir": session.output_dir,
            "artifacts_dir": session.artifacts_dir,
            "session_dirname": session.session_dirname,
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "session_id": session_id,
            "html_name": session.input_html_name,
        },
    )
    return context
