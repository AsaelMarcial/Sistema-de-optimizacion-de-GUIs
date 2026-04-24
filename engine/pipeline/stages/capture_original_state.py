from __future__ import annotations

from engine.adapters.browser.css_overview import build_css_overview_from_models
from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.models.color import ColorCatalog
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import Session
from engine.domain.models.style import StyleCatalog
from engine.domain.utils.color_usage import build_color_usage_catalog
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.snapshot_validators import has_snapshot_structure


def _session_ready_for_capture(session: Session) -> bool:
    return (
        bool(session.input_html_content.strip())
        and bool(session.input_base_path.strip())
        and bool(session.original_screenshot_path.strip())
    )


CONTRACT = StageContract(
    name="capture_original_state",
    requires=(
        context_value("session.page_builder", PageBuilder),
        context_value("session", Session, validator=_session_ready_for_capture),
    ),
    produces=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("style.catalog", StyleCatalog),
        context_value("color.catalog", ColorCatalog),
        context_value("derived.raw_css_overview", dict),
        context_value("derived.raw_snapshot_metadata", dict),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    session = context.get("session")
    if context.error or context.has("prototype_structure"):
        return context

    screenshot_filename = session.ORIGINAL_SCREENSHOT_NAME
    context.trace.add_stage_event(
        CONTRACT.name,
        "start",
        {
            "base_path": session.input_base_path,
            "output_image": session.original_screenshot_path,
        },
    )
    artifacts = context.get("session.page_builder").capture_state_artifacts(
        artifacts_dir=session.artifacts_dir,
        screenshot_filename=screenshot_filename,
    )
    snapshot = artifacts.snapshot
    if not has_snapshot_structure(snapshot):
        return context.set_error("Render capture bundle does not contain a valid snapshot structure.")

    styles_inventory = StyleCatalog.build(artifacts.styles_inventory_seed or StyleCatalog())
    seed_inventory = ColorCatalog.build(artifacts.colors_inventory_seed or ColorCatalog())
    prototype_structure = PrototypeStructure.build(
        snapshot.nodes,
        styles_inventory=styles_inventory,
    )
    colors_inventory = build_color_usage_catalog(
        prototype_structure,
        existing_inventory=seed_inventory,
    )
    css_overview = build_css_overview_from_models(
        prototype_structure,
        styles_inventory,
        colors_inventory,
    )

    context.set("prototype_structure", prototype_structure)
    context.set("style.catalog", styles_inventory)
    context.set("color.catalog", colors_inventory)
    context.set("derived.raw_css_overview", css_overview)
    context.set("derived.raw_snapshot_metadata", dict(snapshot.metadata))

    context.trace.add_step(
        "before_prototype.render_done",
        {
            "screenshot_path": artifacts.screenshot_path,
            "snapshot_node_count": artifacts.snapshot.metadata.get("nodeCount"),
        },
    )
    context.trace.add_step(
        "analysis.render_snapshot_generated",
        {
            "snapshot_path": None,
            "node_count": artifacts.snapshot.metadata.get("nodeCount"),
        },
    )
    context.trace.add_step(
        "prototype_structure.captured",
        {
            "prototype_node_count": len(prototype_structure),
            "style_rule_count": len(styles_inventory),
            "observed_color_count": len(colors_inventory),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "node_count": artifacts.snapshot.metadata.get("nodeCount"),
            "prototype_node_count": len(prototype_structure),
            "style_rule_count": len(styles_inventory),
            "observed_color_count": len(colors_inventory),
        },
    )
    return context
