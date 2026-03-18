from __future__ import annotations

from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.environmental_assessment.stage import (
    run_environmental_assessment_stage,
)


def run_estimate_original_carbonfootprint_stage(context: PipelineContext) -> None:
    run_environmental_assessment_stage(context)
