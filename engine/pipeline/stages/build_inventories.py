from __future__ import annotations

from copy import deepcopy

from engine.adapters.utils.io import save_json
from engine.domain.models.element import ElementColorPropertyModel, ElementInventoryModel
from engine.domain.models.snapshot import RenderSnapshot
from engine.domain.models.style import StyleInventoryModel
from engine.domain.models.color import ColorInventoryModel
from engine.pipeline.artifact_serializers import (
    build_colors_inventory_artifact,
    build_elements_inventory_artifact,
    build_styles_inventory_artifact,
)
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.snapshot_validators import has_snapshot_structure

CONTRACT = StageContract(
    name="build_inventories",
    requires=(
        context_value(
            "session.artifacts.original.snapshot",
            RenderSnapshot,
            validator=has_snapshot_structure,
        ),
        context_value("session.artifacts.original.styles_inventory_seed", StyleInventoryModel),
        context_value("session.artifacts.original.colors_inventory_seed", ColorInventoryModel),
        context_value("session.artifacts.original.css_overview", dict),
        context_value(
            "session.output.paths.original.elements_inventory_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.original.styles_inventory_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.original.colors_inventory_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.original.css_overview_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
    ),
    produces=(
        context_value("elements.inventory", ElementInventoryModel),
        context_value("style.inventory", StyleInventoryModel),
        context_value("color.inventory", ColorInventoryModel),
    ),
)

_CSS_OVERVIEW_COLOR_ROLES = ("text", "background", "border", "fill", "stroke")


def _observed_color_payloads(css_overview: dict) -> list[dict]:
    payloads: list[dict] = []
    colors_by_role = dict(css_overview.get("colors") or {})
    for role in _CSS_OVERVIEW_COLOR_ROLES:
        for entry in colors_by_role.get(role) or ():
            value = str(entry.get("css") or entry.get("hex") or "").strip()
            if not value:
                continue
            node_ids = tuple(
                str(item).strip()
                for item in (entry.get("node_ids") or ())
                if str(item).strip()
            )
            count = int(entry.get("count") or len(node_ids) or 0)
            payloads.append(
                {
                    "value": value,
                    "usage_count": len(node_ids) or count,
                    "node_ids": list(node_ids),
                    "observed_usage_count": len(node_ids) or count,
                    "observed_roles": [
                        {
                            "role": role,
                            "count": count,
                            "node_ids": list(node_ids),
                            "sample_selectors": [
                                str(item).strip()
                                for item in (entry.get("sample_selectors") or ())
                                if str(item).strip()
                            ],
                        }
                    ],
                    "declared_in_snapshot": False,
                }
            )
    return payloads


def _merge_colors_inventory_with_css_overview(
    colors_inventory_seed: ColorInventoryModel,
    css_overview: dict,
) -> ColorInventoryModel:
    observed_payloads = _observed_color_payloads(css_overview)
    return ColorInventoryModel.build([*colors_inventory_seed, *observed_payloads])


def _link_css_overview_to_color_inventory(
    css_overview: dict,
    colors_inventory: ColorInventoryModel,
) -> dict:
    linked = deepcopy(css_overview)
    linked_colors: dict[str, list[dict]] = {}
    for role in _CSS_OVERVIEW_COLOR_ROLES:
        role_entries: list[dict] = []
        for entry in (dict(linked.get("colors") or {})).get(role) or ():
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


def _build_element_color_properties(
    elements_inventory: ElementInventoryModel,
    colors_inventory: ColorInventoryModel,
) -> ElementInventoryModel:
    built_entries = []
    for element in elements_inventory:
        color_properties = []
        for index, (property_name, computed_style) in enumerate(
            sorted(element.iter_computed_styles(), key=lambda item: item[0]),
            start=1,
        ):
            color_entry = colors_inventory.entry_by_value(computed_style.computed_value)
            if color_entry is None:
                continue
            color_properties.append(
                ElementColorPropertyModel.from_computed_style(
                    node_id=element.node_id,
                    index=index,
                    property_name=property_name,
                    computed_style=computed_style,
                    color_id=color_entry.color_id,
                )
            )

        effective_background_color_id = None
        if element.styles.effective_background:
            background_entry = colors_inventory.entry_by_value(element.styles.effective_background)
            if background_entry is not None:
                effective_background_color_id = background_entry.color_id

        built_entries.append(
            element.with_color_properties(
                tuple(color_properties),
                effective_background_color_id=effective_background_color_id,
            )
        )

    return ElementInventoryModel.build(built_entries)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context
    if context.has("elements.inventory") and context.has("style.inventory") and context.has("color.inventory"):
        return context

    snapshot = context.get("session.artifacts.original.snapshot")
    styles_inventory_seed = context.get("session.artifacts.original.styles_inventory_seed")
    colors_inventory_seed = context.get("session.artifacts.original.colors_inventory_seed")
    css_overview = context.get("session.artifacts.original.css_overview")
    context.trace.add_stage_event(CONTRACT.name, "start")

    elements_inventory = snapshot.build_elements_inventory()
    styles_inventory = StyleInventoryModel.build(styles_inventory_seed)
    colors_inventory = _merge_colors_inventory_with_css_overview(
        ColorInventoryModel.build(colors_inventory_seed),
        css_overview,
    )
    elements_inventory = _build_element_color_properties(elements_inventory, colors_inventory)
    linked_css_overview = _link_css_overview_to_color_inventory(css_overview, colors_inventory)

    context.set("elements.inventory", elements_inventory)
    context.set("style.inventory", styles_inventory)
    context.set("color.inventory", colors_inventory)
    context.set("session.artifacts.original.css_overview", linked_css_overview)
    save_json(
        context.get("session.output.paths.original.elements_inventory_json"),
        build_elements_inventory_artifact(elements_inventory),
        indent=4,
    )
    save_json(
        context.get("session.output.paths.original.styles_inventory_json"),
        build_styles_inventory_artifact(styles_inventory),
        indent=4,
    )
    save_json(
        context.get("session.output.paths.original.colors_inventory_json"),
        build_colors_inventory_artifact(colors_inventory),
        indent=4,
    )
    save_json(
        context.get("session.output.paths.original.css_overview_json"),
        linked_css_overview,
        indent=4,
    )

    context.trace.add_step(
        "inventories.built",
        {
            "elements_count": len(elements_inventory),
            "styles_count": len(styles_inventory),
            "colors_count": len(colors_inventory),
            "observed_color_count": sum(
                1 for color_entry in colors_inventory if color_entry.observed_usage_count > 0
            ),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "elements_count": len(elements_inventory),
            "styles_count": len(styles_inventory),
            "colors_count": len(colors_inventory),
        },
    )
    return context
