from __future__ import annotations

from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.transformation.apply_heuristics import apply_heuristics
from engine.pipeline.stages.transformation.load_transformed_html import load_transformed_html
from engine.pipeline.stages.transformation.stage_assets import stage_assets


def run_transformation_stage(context: PipelineContext) -> None:
    if context.error:
        return

    stage_assets(context)
    if context.error:
        return
    apply_heuristics(context)
    if context.error:
        return
    load_transformed_html(context)
