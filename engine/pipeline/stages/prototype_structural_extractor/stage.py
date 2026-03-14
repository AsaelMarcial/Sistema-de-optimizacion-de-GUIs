from __future__ import annotations

from engine.models.pipeline_context import PipelineContext
from engine.models.prototype_structural_extractor.snapshot_models import SnapshotOptions
from engine.services.prototype_structural_extractor.render_snapshot_service import (
    capture_prototype_state_artifacts,
)


def _capture(context: PipelineContext, *, transformed: bool) -> None:
    label = "environmental_prototype" if transformed else "original_prototype"
    base_path = (context.output_dir or "") if transformed else (context.base_path or "")
    html_content = (context.transformed_html_content or "") if transformed else (context.html_content or "")
    output_image_path = (
        context.environmental_screenshot_path if transformed else context.original_screenshot_path
    )
    output_json_path = None if transformed else context.original_snapshot_path

    context.trace.add_step(
        f"{label}.render_start",
        {
            "base_path": base_path,
            "output_image": output_image_path,
        },
    )

    artifacts = capture_prototype_state_artifacts(
        html_content=html_content,
        base_path=base_path,
        options=SnapshotOptions(include_color_frequencies=True),
        output_json_path=output_json_path,
        output_image_path=output_image_path,
        session_id=context.session_id,
    )

    if transformed:
        context.environmental_artifacts = artifacts
    else:
        context.original_artifacts = artifacts

    context.trace.add_step(
        f"{label}.render_done",
        {
            "screenshot_path": artifacts.screenshot_path,
            "snapshot_node_count": artifacts.snapshot.metadata.get("nodeCount"),
        },
    )
    if artifacts.color_frequencies is not None:
        context.trace.add_step(
            f"{label}.colors_classified",
            {"distinct_colors": len(artifacts.color_frequencies)},
        )
    if not transformed:
        context.trace.add_step(
            "analysis.render_snapshot_generated",
            {
                "snapshot_path": context.original_snapshot_path,
                "node_count": artifacts.snapshot.metadata.get("nodeCount"),
            },
        )


def run_prototype_structural_extractor_stage(context: PipelineContext) -> None:
    if context.error:
        return

    if context.original_artifacts is None:
        _capture(context, transformed=False)
        return

    if context.transformed_html_content and context.environmental_artifacts is None:
        _capture(context, transformed=True)
