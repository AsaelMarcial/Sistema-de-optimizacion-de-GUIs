from __future__ import annotations

from engine.domain.models.color import ColorInventoryEntry, build_inventory_from_scheme_colors
from engine.domain.models.element import Element, Property
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.quality_reports import (
    ContrastColorReference,
    ContrastIssue,
    ContrastReport,
)
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

_FOREGROUND_PROPERTY_NAMES = ("color", "fill", "stroke", "text-decoration-color", "outline-color")
_BACKGROUND_PROPERTY_NAMES = ("background-color", "background")


def _session_ready_for_contrast(session: Session) -> bool:
    return session.original_css_overview is not None


CONTRACT = StageContract(
    name="build_contrast_report",
    requires=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("scheme.colors", tuple),
        context_value("session", Session, validator=_session_ready_for_contrast),
    ),
    produces=(context_value("derived.contrast_report", ContrastReport),),
)


def _resolve_color_source(
    prototype_structure: PrototypeStructure,
    *,
    element: Element,
    color_entry: ColorInventoryEntry | None,
    property_names: tuple[str, ...],
) -> tuple[Element | None, Property | None]:
    if color_entry is None:
        return None, None

    candidates = (element, *prototype_structure.ancestors_of(element.node_id))
    for property_name in property_names:
        for candidate in candidates:
            for property_model in candidate.properties:
                if property_model.color_id == color_entry.color_id and property_model.name == property_name:
                    return candidate, property_model

    for candidate in candidates:
        for property_model in candidate.properties:
            if property_model.color_id == color_entry.color_id:
                return candidate, property_model

    return None, None


def _build_color_reference(
    fallback_payload: dict,
    *,
    color_entry: ColorInventoryEntry | None,
    source_element: Element | None,
    source_property: Property | None,
) -> ContrastColorReference:
    return ContrastColorReference(
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
        style_id=source_property.style_id if source_property is not None else None,
        declaration_id=source_property.declaration_id if source_property is not None else None,
        property_name=source_property.name if source_property is not None else None,
        declared_property=source_property.declared_property if source_property is not None else None,
    )


def _build_report(
    css_overview: dict,
    prototype_structure: PrototypeStructure,
    scheme_colors: tuple,
) -> ContrastReport:
    colors_inventory = build_inventory_from_scheme_colors(scheme_colors)
    issues: list[ContrastIssue] = []
    raw_issues = tuple(css_overview.get("contrast_issues") or ())

    for index, raw_issue in enumerate(raw_issues, start=1):
        element_id = str(raw_issue.get("node_id") or "").strip() or None
        element = prototype_structure.node_by_id(element_id) if element_id is not None else None
        foreground_payload = dict(raw_issue.get("foreground") or {})
        background_payload = dict(raw_issue.get("background") or {})

        foreground_entry = colors_inventory.entry_by_value(
            str(foreground_payload.get("css") or foreground_payload.get("hex") or "")
        )
        background_entry = colors_inventory.entry_by_value(
            str(background_payload.get("css") or background_payload.get("hex") or "")
        )

        foreground_source_element = None
        foreground_property = None
        background_source_element = None
        background_property = None
        background_validation = "missing"

        if element is not None:
            foreground_source_element, foreground_property = _resolve_color_source(
                prototype_structure,
                element=element,
                color_entry=foreground_entry,
                property_names=_FOREGROUND_PROPERTY_NAMES,
            )
            background_source_element, background_property = _resolve_color_source(
                prototype_structure,
                element=element,
                color_entry=background_entry,
                property_names=_BACKGROUND_PROPERTY_NAMES,
            )

            effective_background = prototype_structure.effective_background_of(
                element.node_id,
                colors_inventory,
            )
            if effective_background is not None and background_entry is not None:
                background_validation = (
                    "match"
                    if effective_background.color_id == background_entry.color_id
                    else "mismatch"
                )
            elif effective_background is not None:
                background_entry = effective_background
                background_validation = "inventory_only"

            if background_source_element is None:
                background_source_element = prototype_structure.surface_container_of(element.node_id)

        issues.append(
            ContrastIssue(
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
    return ContrastReport(issues=tuple(issues))


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("derived.contrast_report"):
        return context

    context.trace.add_stage_event(CONTRACT.name, "start")
    report = _build_report(
        context.get("session").original_css_overview or {},
        context.get("prototype_structure"),
        tuple(context.get("scheme.colors")),
    )
    context.set("derived.contrast_report", report)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "contrast_issue_count": len(report),
            "linked_issue_count": sum(1 for issue in report if issue.element_id is not None),
        },
    )
    return context
