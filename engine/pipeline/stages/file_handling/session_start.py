from __future__ import annotations

from engine.services.file_handling.session_handler import clean_old_sessions, generate_session_id
from engine.models.pipeline_context import PipelineContext


def start_session(context: PipelineContext) -> None:
    context.session_id = generate_session_id()
    clean_old_sessions(active_session_id=context.session_id)
