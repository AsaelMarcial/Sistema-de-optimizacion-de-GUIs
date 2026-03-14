from __future__ import annotations

from engine.models.pipeline_context import PipelineContext
from engine.pipeline.stages.results.bundle_outputs import bundle_outputs
from engine.pipeline.stages.results.compile_results import compile_final_results


def run_results_stage(context: PipelineContext) -> None:
    if context.error:
        return

    bundle_outputs(context)
    if context.error:
        return
    compile_final_results(context)
