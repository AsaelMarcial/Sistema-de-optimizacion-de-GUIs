from __future__ import annotations

from typing import Any

from engine.models.debug_trace import DebugTrace
from engine.models.pipeline_context import PipelineContext
from engine.models.pipeline_result import PipelineResult
from engine.pipeline.stages.environmental_assessment.stage import run_environmental_assessment_stage
from engine.pipeline.stages.file_handling.stage import run_file_handling_stage
from engine.pipeline.stages.prototype_structural_extractor.stage import (
    run_prototype_structural_extractor_stage,
)
from engine.pipeline.stages.recommendations.stage import run_recommendations_stage
from engine.pipeline.stages.results.stage import run_results_stage
from engine.pipeline.stages.transformation.stage import run_transformation_stage
_STAGE_RUNNERS = (
    run_file_handling_stage,
    run_prototype_structural_extractor_stage,
    run_environmental_assessment_stage,
    run_transformation_stage,
    run_prototype_structural_extractor_stage,
    run_environmental_assessment_stage,
    run_recommendations_stage,
    run_results_stage,
)


def run_pipeline(file) -> tuple[dict[str, Any] | None, str | None]:
    context = PipelineContext(
        file=file,
        trace=DebugTrace(enabled=True),
    )
    for stage_runner in _STAGE_RUNNERS:
        stage_runner(context)
        if context.error:
            break
    return PipelineResult(payload=context.results, error=context.error).to_tuple()
