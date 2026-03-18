from __future__ import annotations

from engine.pipeline.context import PipelineContext
from engine.pipeline.stages.prototype_structural_extractor.stage import (
    run_prototype_structural_extractor_stage,
)


def run_analyze_initial_state_stage(context: PipelineContext) -> None:
    run_prototype_structural_extractor_stage(context)
