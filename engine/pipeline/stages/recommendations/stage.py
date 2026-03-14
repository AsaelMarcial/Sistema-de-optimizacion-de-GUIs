from __future__ import annotations

from engine.models.pipeline_context import PipelineContext
from engine.models.recommendations.recommendations_payload import RecommendationsPayload


def run_recommendations_stage(context: PipelineContext) -> None:
    if context.error:
        return

    context.recommendations = RecommendationsPayload(items=(), summary=None)
