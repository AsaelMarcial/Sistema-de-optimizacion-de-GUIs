from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

from engine.adapters.browser.render_models import RenderArtifacts
from engine.domain.models.color import ColorInventoryModel
from engine.domain.models.prototype_structure import PrototypeStructure, build_observed_color_payloads
from engine.domain.models.session import Session
from engine.domain.models.style import StyleInventoryModel
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.snapshot_validators import has_snapshot_structure


def _captured_session(session: Session) -> bool:
    return isinstance(session.original_capture, RenderArtifacts)


CONTRACT = StageContract(
    name="capture_prototype_structure",
    requires=(
        context_value("session", Session, validator=_captured_session),
    ),
    produces=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("session", Session),
    ),
)


def _link_css_overview_to_color_inventory(
    css_overview: dict,
    colors_inventory: ColorInventoryModel,
) -> dict:
    linked = deepcopy(css_overview)
    linked_colors: dict[str, list[dict]] = {}
    for role, raw_entries in sorted(dict(linked.get("colors") or {}).items()):
        role_entries: list[dict] = []
        for entry in raw_entries or ():
            color_entry = colors_inventory.entry_by_value(str(entry.get("css") or entry.get("hex") or ""))
            role_entry = {
                "count": int(entry.get("count") or 0),
                "node_ids": [
                    str(item).strip()
                    for item in (entry.get("node_ids") or ())
                    if str(item).strip()
                ],
                "sample_selectors": [
                    str(item).strip()
                    for item in (entry.get("sample_selectors") or ())
                    if str(item).strip()
                ],
            }
            if color_entry is not None:
                role_entry["color_id"] = color_entry.color_id
            role_entries.append(role_entry)
        linked_colors[role] = role_entries
    linked["colors"] = linked_colors
    return linked


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context
    if context.has("prototype_structure"):
        return context

    session = context.get("session")
    capture = session.original_capture
    context.trace.add_stage_event(CONTRACT.name, "start")

    snapshot = capture.snapshot
    styles_inventory_seed = capture.styles_inventory_seed or StyleInventoryModel()
    colors_inventory_seed = capture.colors_inventory_seed or ColorInventoryModel()
    css_overview = capture.css_overview or {}

    if not has_snapshot_structure(snapshot):
        return context.set_error("Render capture bundle does not contain a valid snapshot structure.")

    styles_inventory = StyleInventoryModel.build(styles_inventory_seed)
    seed_inventory = ColorInventoryModel.build(colors_inventory_seed)
    colors_inventory = ColorInventoryModel.build(
        [
            *seed_inventory,
            *build_observed_color_payloads(
                css_overview,
                existing_inventory=seed_inventory,
            ),
        ]
    )
    prototype_structure = PrototypeStructure.build(
        snapshot.nodes,
        styles_inventory=styles_inventory,
    )
    colors_inventory = prototype_structure.build_color_inventory(
        css_overview=css_overview,
        existing_inventory=colors_inventory,
    )
    linked_css_overview = _link_css_overview_to_color_inventory(css_overview, colors_inventory)

    context.set("prototype_structure", prototype_structure)
    context.set(
        "session",
        replace(
            session,
            original_capture=None,
            original_css_overview=linked_css_overview,
            original_snapshot_metadata=dict(snapshot.metadata),
        ),
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
            "prototype_node_count": len(prototype_structure),
            "style_rule_count": len(styles_inventory),
            "observed_color_count": len(colors_inventory),
        },
    )
    return context
