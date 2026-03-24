from __future__ import annotations

from engine.adapters.browser.snapshot_analyzer import extract_prototype_css_overview
from engine.adapters.browser.snapshot_analyzer import capture_prototype_state_artifacts
from engine.adapters.utils.io import save_json
from engine.domain.models.color import ColorInventoryModel
from engine.domain.models.snapshot import RenderSnapshot, SnapshotOptions
from engine.domain.models.style import StyleInventoryModel
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
        context_value("session.artifacts.original.snapshot", RenderSnapshot),
        context_value("session.artifacts.original.screenshot", str, validator=lambda value: bool(value.strip())),
        context_value("session.artifacts.original.pixel_frequencies_raw", list),
        context_value("session.artifacts.original.styles_inventory_seed", StyleInventoryModel),
        context_value("session.artifacts.original.colors_inventory_seed", ColorInventoryModel),
        context_value("session.artifacts.original.css_overview", dict),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("session.artifacts.original.snapshot"):
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
        output_json_path=context.get("session.output.paths.original.snapshot_json"),
        output_image_path=output_image_path,
        session_id=context.get("session.output.id"),
    )
    color_frequencies = list(artifacts.color_frequencies or [])
    context.set("session.artifacts.original.snapshot", artifacts.snapshot)
    context.set("session.artifacts.original.screenshot", artifacts.screenshot_path or output_image_path)
    context.set("session.artifacts.original.pixel_frequencies_raw", color_frequencies)
    context.set(
        "session.artifacts.original.styles_inventory_seed",
        artifacts.styles_inventory_seed,
    )
    context.set(
        "session.artifacts.original.colors_inventory_seed",
        artifacts.colors_inventory_seed,
    )
    css_overview = extract_prototype_css_overview(
        html_content=context.get("session.input.html.content", ""),
        base_path=base_path,
        options=SnapshotOptions(capture_screenshot=False),
    )
    context.set("session.artifacts.original.css_overview", css_overview)
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
