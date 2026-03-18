from __future__ import annotations

from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.color_processing.stage import run_color_processing_stage


def run_build_color_schema_stage(context: PipelineContext) -> None:
    run_color_processing_stage(context)
