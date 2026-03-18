from __future__ import annotations

from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.recommendations.stage import run_recommendations_stage
from engine.pipeline.stages.results.stage import run_results_stage


def run_report_obtained_results_stage(context: PipelineContext) -> None:
    run_recommendations_stage(context)
    if context.error:
        return
    run_results_stage(context)
