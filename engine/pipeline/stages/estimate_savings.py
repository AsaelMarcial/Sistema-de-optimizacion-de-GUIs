from __future__ import annotations

from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.environmental_assessment.stage import (
    run_environmental_assessment_stage,
)
from engine.pipeline.stages.prototype_structural_extractor.stage import (
    run_prototype_structural_extractor_stage,
)


def run_estimate_savings_stage(context: PipelineContext) -> None:
    run_prototype_structural_extractor_stage(context)
    if context.error:
        return
    run_environmental_assessment_stage(context)
