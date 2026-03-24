from __future__ import annotations

from engine.adapters.utils.io import save_json
from engine.domain.models.color import ColorInventoryEntry
from engine.domain.models.contrast import (
    ContrastColorReferenceModel,
    ContrastIssueModel,
    ContrastReportModel,
)
from engine.domain.models.element import ElementColorPropertyModel, ElementInventoryEntry
from engine.domain.models.inventory_graph import InventoryGraphModel
from engine.domain.models.style import StyleInventoryModel
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

_FOREGROUND_PROPERTY_NAMES = ("color", "fill", "stroke", "text-decoration-color", "outline-color")
_BACKGROUND_PROPERTY_NAMES = ("background-color", "background")

CONTRACT = StageContract(
    name="build_contrast_report",
    requires=(
        context_value("elements.inventory"),
        context_value("style.inventory", StyleInventoryModel),
        context_value("color.inventory"),
        context_value("session.artifacts.original.css_overview", dict),
        context_value(
            "session.output.paths.original.contrast_report_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
    ),
    produces=(context_value("inventory.contrast_report", ContrastReportModel),),
)


def _resolve_color_source(
    inventory_graph: InventoryGraphModel,
    *,
    element: ElementInventoryEntry,
    color_entry: ColorInventoryEntry | None,
    property_names: tuple[str, ...],
) -> tuple[ElementInventoryEntry | None, ElementColorPropertyModel | None]:
    if color_entry is None:
        return None, None

    candidates = (element, *inventory_graph.ancestors_of(element.node_id))
    for property_name in property_names:
        for candidate in candidates:
            for color_property in candidate.color_properties:
                if color_property.color_id == color_entry.color_id and color_property.property_name == property_name:
                    return candidate, color_property

    for candidate in candidates:
        for color_property in candidate.color_properties:
            if color_property.color_id == color_entry.color_id:
                return candidate, color_property

    return None, None


def _build_color_reference(
    fallback_payload: dict,
    *,
    color_entry: ColorInventoryEntry | None,
    source_element: ElementInventoryEntry | None,
    source_property: ElementColorPropertyModel | None,
) -> ContrastColorReferenceModel:
    winning_style_ref = source_property.winning_style_ref if source_property is not None else None
    return ContrastColorReferenceModel(
        css=str(fallback_payload.get("css") or ""),
        hex_value=str(
            fallback_payload.get("hex")
            or (color_entry.hex_value if color_entry is not None else "")
        ),
        alpha=float(
            fallback_payload.get("alpha")
            if fallback_payload.get("alpha") is not None
            else (color_entry.alpha if color_entry is not None else 0.0)
        ),
        color_id=color_entry.color_id if color_entry is not None else None,
        element_id=source_element.node_id if source_element is not None else None,
        color_property_id=source_property.color_property_id if source_property is not None else None,
        style_id=winning_style_ref.style_id if winning_style_ref is not None else None,
        declaration_id=(
            winning_style_ref.declaration_id if winning_style_ref is not None else None
        ),
        property_name=source_property.property_name if source_property is not None else None,
        declared_property=(
            winning_style_ref.declared_property if winning_style_ref is not None else None
        ),
    )


def _build_report(
    css_overview: dict,
    inventory_graph: InventoryGraphModel,
) -> ContrastReportModel:
    issues: list[ContrastIssueModel] = []
    raw_issues = tuple(css_overview.get("contrast_issues") or ())

    for index, raw_issue in enumerate(raw_issues, start=1):
        element_id = str(raw_issue.get("node_id") or "").strip() or None
        element = (
            inventory_graph.element_by_id(element_id)
            if element_id is not None
            else None
        )
        foreground_payload = dict(raw_issue.get("foreground") or {})
        background_payload = dict(raw_issue.get("background") or {})

        foreground_entry = inventory_graph.colors.entry_by_value(
            str(foreground_payload.get("css") or foreground_payload.get("hex") or "")
        )
        background_entry = inventory_graph.colors.entry_by_value(
            str(background_payload.get("css") or background_payload.get("hex") or "")
        )

        foreground_source_element = None
        foreground_property = None
        background_source_element = None
        background_property = None
        background_validation = "missing"

        if element is not None:
            foreground_source_element, foreground_property = _resolve_color_source(
                inventory_graph,
                element=element,
                color_entry=foreground_entry,
                property_names=_FOREGROUND_PROPERTY_NAMES,
            )
            background_source_element, background_property = _resolve_color_source(
                inventory_graph,
                element=element,
                color_entry=background_entry,
                property_names=_BACKGROUND_PROPERTY_NAMES,
            )

            effective_background = inventory_graph.effective_background_of(element.node_id)
            if effective_background is not None and background_entry is not None:
                background_validation = (
                    "match"
                    if effective_background.color_id == background_entry.color_id
                    else "mismatch"
                )
            elif effective_background is not None:
                background_entry = effective_background
                background_validation = "inventory_only"

            if background_source_element is None and element is not None:
                background_source_element = inventory_graph.surface_container_of(element.node_id)

        issues.append(
            ContrastIssueModel(
                issue_id=f"contrast-{index}",
                element_id=element.node_id if element is not None else element_id,
                selector=str(raw_issue.get("selector") or ""),
                tag_name=str(raw_issue.get("tag_name") or ""),
                text_sample=str(raw_issue.get("text_sample") or ""),
                contrast_ratio=float(raw_issue.get("contrast_ratio") or 0.0),
                required_ratio=float(raw_issue.get("required_ratio") or 0.0),
                is_large_text=bool(raw_issue.get("is_large_text", False)),
                font_size_px=float(raw_issue.get("font_size_px") or 0.0),
                font_weight=int(raw_issue.get("font_weight") or 0),
                bounds=dict(raw_issue.get("bounds") or {}),
                foreground=_build_color_reference(
                    foreground_payload,
                    color_entry=foreground_entry,
                    source_element=foreground_source_element,
                    source_property=foreground_property,
                ),
                background=_build_color_reference(
                    background_payload,
                    color_entry=background_entry,
                    source_element=background_source_element,
                    source_property=background_property,
                ),
                background_validation=background_validation,
            )
        )

    issues.sort(key=lambda issue: (issue.contrast_ratio, issue.selector, issue.issue_id))
    return ContrastReportModel(issues=tuple(issues))


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("inventory.contrast_report"):
        return context

    inventory_graph = InventoryGraphModel.build(
        elements=context.get("elements.inventory"),
        styles=context.get("style.inventory"),
        colors=context.get("color.inventory"),
    )
    context.trace.add_stage_event(CONTRACT.name, "start")
    report = _build_report(
        context.get("session.artifacts.original.css_overview"),
        inventory_graph,
    )
    context.set("inventory.contrast_report", report)
    save_json(
        context.get("session.output.paths.original.contrast_report_json"),
        report.to_dict(),
        indent=4,
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "contrast_issue_count": len(report),
            "linked_issue_count": sum(1 for issue in report if issue.element_id is not None),
        },
    )
    return context
