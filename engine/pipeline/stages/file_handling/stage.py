from __future__ import annotations

from engine.models.pipeline_context import PipelineContext
from engine.pipeline.stages.file_handling.project_load import load_project
from engine.pipeline.stages.file_handling.session_start import start_session


def run_file_handling_stage(context: PipelineContext) -> None:
    if context.error:
        return

    start_session(context)
    if context.error:
        return
    load_project(context)
