from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.models.color import ColorCatalog
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.quality_reports import ColorUsages
from pathlib import Path

from engine.domain.models.session import Session
from engine.domain.models.style import StyleCatalog
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.snapshot_validators import has_snapshot_structure


def _session_ready_for_capture(session: Session) -> bool:
    try:
        candidates = session.find_by_suffix("before", ("html",))
        return len(candidates) == 1 and candidates[0].exists()
    except (FileNotFoundError, RuntimeError, ValueError, OSError):
        return False


CONTRACT = StageContract(
    name="capture_original_state",
    requires=(
        context_value(K.PAGE_BUILDER, PageBuilder),
        context_value(K.SESSION, Session, validator=_session_ready_for_capture),
    ),
    produces=(
        context_value(K.PROTOTYPE_STRUCTURE, PrototypeStructure),
        context_value(K.STYLE_CATALOG, StyleCatalog),
        context_value(K.COLOR_CATALOG, ColorCatalog),
        context_value(K.DERIVED_COLOR_USAGES, ColorUsages),
        context_value(K.DERIVED_RAW_SNAPSHOT_METADATA, dict),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    session = context.get(K.SESSION)
    if context.error or context.has(K.PROTOTYPE_STRUCTURE):
        return context

    context.trace.add_stage_event(
        CONTRACT.name,
        "start",
        {
            "base_path": str(session.find_by_suffix("before", ("html",))[0].parent),
            "output_image": str(session.get_path("before.png", "artifacts", "png")),
        },
    )
    page_builder = context.get(K.PAGE_BUILDER)
    before_screenshot = session.get_path("before.png", "artifacts", "png")
    screenshot_path = page_builder.capture_full_page_screenshot(
        output_path=before_screenshot,
    )
    snapshot, styles_inventory = page_builder.capture_snapshot_models()
    if not has_snapshot_structure(snapshot):
        return context.set_error("Render capture bundle does not contain a valid snapshot structure.")

    prototype_structure = PrototypeStructure.build(snapshot.nodes)
    colors_inventory = ColorCatalog()
    color_usages = ColorUsages()
    for element in prototype_structure:
        for property_model in element.properties:
            property_id = property_model.property_id or property_model.name
            color_ids: list[str] = []
            for color_value in property_model.color_values():
                color_id = colors_inventory.add_color(color_value)
                color_ids.append(color_id)
                color_usages.add(
                    color_id=color_id,
                    property_name=property_id,
                    element_id=element.node_id,
            )
            property_model.set_color_ids(color_ids)

    context.set(K.PROTOTYPE_STRUCTURE, prototype_structure)
    context.set(K.STYLE_CATALOG, styles_inventory)
    context.set(K.COLOR_CATALOG, colors_inventory)
    context.set(K.DERIVED_COLOR_USAGES, color_usages)
    context.set(K.DERIVED_RAW_SNAPSHOT_METADATA, dict(snapshot.metadata))

    context.trace.add_step(
        "before_prototype.render_done",
        {
            "screenshot_path": screenshot_path,
            "snapshot_node_count": snapshot.metadata.get("nodeCount"),
        },
    )
    context.trace.add_step(
        "analysis.render_snapshot_generated",
        {
            "snapshot_path": None,
            "node_count": snapshot.metadata.get("nodeCount"),
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
            "node_count": snapshot.metadata.get("nodeCount"),
            "prototype_node_count": len(prototype_structure),
            "style_rule_count": len(styles_inventory),
            "observed_color_count": len(colors_inventory),
        },
    )
    return context
