from __future__ import annotations

from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.file_handling.stage import run_file_handling_stage


def run_process_file_stage(context: PipelineContext) -> None:
    run_file_handling_stage(context)
