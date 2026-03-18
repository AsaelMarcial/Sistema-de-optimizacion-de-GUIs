from __future__ import annotations

from engine.pipeline.context import PipelineContext


def run_check_tokens_stage(context: PipelineContext) -> None:
    """
    TODO: Validate and normalize generated tokens before applying transformations.
    """
    _ = context
