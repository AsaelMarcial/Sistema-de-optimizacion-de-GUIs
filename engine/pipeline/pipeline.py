from __future__ import annotations

from typing import Any

from engine.pipeline.context import PipelineContext
from engine.pipeline.debug_trace import DebugTrace
from engine.pipeline.result import PipelineResult
from engine.pipeline.stages.analyze_initial_state import run_analyze_initial_state_stage
from engine.pipeline.stages.apply_transformations import run_apply_transformations_stage
from engine.pipeline.stages.build_color_schema import run_build_color_schema_stage
from engine.pipeline.stages.estimate_original_carbonfootprint import (
    run_estimate_original_carbonfootprint_stage,
)
from engine.pipeline.stages.estimate_savings import run_estimate_savings_stage
from engine.pipeline.stages.process_file import run_process_file_stage
from engine.pipeline.stages.report_obtained_results import run_report_obtained_results_stage
_STAGE_RUNNERS = (
    run_process_file_stage,
    run_analyze_initial_state_stage,
    run_build_color_schema_stage,
    run_estimate_original_carbonfootprint_stage,
    run_apply_transformations_stage,
    run_estimate_savings_stage,
    run_report_obtained_results_stage,
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
