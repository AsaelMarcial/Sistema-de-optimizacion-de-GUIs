from __future__ import annotations

from engine.pipeline.context import PipelineContext
from engine.services.transformation.heuristic_evaluator import evaluate_and_apply_heuristics


def apply_heuristics(context: PipelineContext) -> None:
    context.heuristics_results = evaluate_and_apply_heuristics(
        context.html_content,
        context.html_path,
        context.output_dir,
        context.session_id,
    )
    context.trace.add_step(
        "transformed.heuristics_applied",
        {
            "heuristics_count": (
                len(context.heuristics_results)
                if hasattr(context.heuristics_results, "__len__")
                else None
            )
        },
    )
