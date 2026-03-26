from __future__ import annotations

from engine.adapters.browser.snapshot_analyzer import capture_prototype_state_artifacts
from engine.adapters.utils.io import save_json
from engine.domain.models.snapshot import RenderArtifacts, SnapshotOptions
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="capture_original_state",
    requires=(
        context_value("session.input.html.content", str, validator=lambda value: bool(value.strip())),
        context_value("session.input.base_path", str, validator=lambda value: bool(value.strip())),
        context_value(
            "session.output.paths.original.snapshot_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.original.screenshot_png",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.original.css_overview_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value("session.output.id", str, validator=lambda value: bool(value.strip())),
    ),
    produces=(
        context_value("session.artifacts.original.capture", RenderArtifacts),
        context_value("session.artifacts.original.screenshot", str, validator=lambda value: bool(value.strip())),
        context_value("session.artifacts.original.pixel_frequencies_raw", list),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("session.artifacts.original.capture"):
        return context

    base_path = context.get("session.input.base_path", "")
    output_image_path = context.get("session.output.paths.original.screenshot_png", "")
    context.trace.add_stage_event(
        CONTRACT.name,
        "start",
        {
            "base_path": base_path,
            "output_image": output_image_path,
        },
    )
    artifacts = capture_prototype_state_artifacts(
        html_content=context.get("session.input.html.content", ""),
        base_path=base_path,
        options=SnapshotOptions(include_color_frequencies=True),
        output_json_path=None,
        output_image_path=output_image_path,
        session_id=context.get("session.output.id"),
    )
    color_frequencies = list(artifacts.color_frequencies or [])
    context.set("session.artifacts.original.capture", artifacts)
    context.set("session.artifacts.original.screenshot", artifacts.screenshot_path or output_image_path)
    context.set("session.artifacts.original.pixel_frequencies_raw", color_frequencies)
    css_overview = artifacts.css_overview or {}
    if context.has("session.output.paths.original.pixel_frequencies_raw_json"):
        save_json(
            context.get("session.output.paths.original.pixel_frequencies_raw_json"),
            color_frequencies,
            indent=4,
        )

    context.trace.add_step(
        "original_prototype.render_done",
        {
            "screenshot_path": artifacts.screenshot_path,
            "snapshot_node_count": artifacts.snapshot.metadata.get("nodeCount"),
        },
    )
    context.trace.add_step(
        "original_prototype.colors_classified",
        {"distinct_colors": len(color_frequencies)},
    )
    context.trace.add_step(
        "analysis.render_snapshot_generated",
        {
            "snapshot_path": context.get("session.output.paths.original.snapshot_json"),
            "node_count": artifacts.snapshot.metadata.get("nodeCount"),
        },
    )
    context.trace.add_step(
        "analysis.css_overview_captured",
        {
            "unused_declaration_count": css_overview.get("unused_declarations", {}).get("count", 0),
            "contrast_issue_count": len(css_overview.get("contrast_issues", [])),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "node_count": artifacts.snapshot.metadata.get("nodeCount"),
            "distinct_colors": len(color_frequencies),
            "css_overview_path": context.get("session.output.paths.original.css_overview_json"),
        },
    )
    return context
