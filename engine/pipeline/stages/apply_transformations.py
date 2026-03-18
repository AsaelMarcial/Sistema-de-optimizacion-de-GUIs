from __future__ import annotations

from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.transformation.stage import run_transformation_stage


def run_apply_transformations_stage(context: PipelineContext) -> None:
    run_transformation_stage(context)
