from __future__ import annotations

from engine.adapters.browser.css_overview import build_css_overview_from_models
from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.models.color import ColorCatalog
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import BEFORE_SCREENSHOT, Session
from engine.domain.models.style import StyleCatalog
from engine.domain.utils.color_usage import build_color_usage_catalog
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.project_uploaded import single_html_file
from engine.validators.snapshot_validators import has_snapshot_structure


def _session_ready_for_capture(session: Session) -> bool:
    try:
        return session.build_path("before", single_html_file(session.file_paths)).exists()
    except Exception:
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
        context_value(K.DERIVED_RAW_CSS_OVERVIEW, dict),
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
            "base_path": str(session.build_path("before", session.project_root_file_path())),
            "output_image": str(session.build_path("artifacts", BEFORE_SCREENSHOT)),
        },
    )
    page_builder = context.get(K.PAGE_BUILDER)
    screenshot_path = page_builder.capture_full_page_screenshot(
        output_path=session.build_path("artifacts", BEFORE_SCREENSHOT),
    )
    snapshot, styles_inventory, seed_inventory = page_builder.capture_snapshot_models()
    if not has_snapshot_structure(snapshot):
        return context.set_error("Render capture bundle does not contain a valid snapshot structure.")

    seed_inventory = ColorCatalog.build(seed_inventory)
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

    context.set(K.PROTOTYPE_STRUCTURE, prototype_structure)
    context.set(K.STYLE_CATALOG, styles_inventory)
    context.set(K.COLOR_CATALOG, colors_inventory)
    context.set(K.DERIVED_RAW_CSS_OVERVIEW, css_overview)
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
