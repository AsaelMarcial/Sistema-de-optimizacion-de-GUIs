from __future__ import annotations

from typing import Any

from engine.adapters.color_service import color_registry
from engine.domain.models.color import Color, ColorCatalog
from engine.domain.models.element import Element, Property
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.quality_reports import (
    ContrastColorReference,
    ContrastIssue,
    ContrastReport,
)
from engine.domain.enums.types.quality import ContrastBackgroundValidation
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value

_FOREGROUND_PROPERTY_NAMES = ("color", "fill", "stroke", "text-decoration-color", "outline-color")
_BACKGROUND_PROPERTY_NAMES = ("background-color", "background")


CONTRACT = StageContract(
    name="build_contrast_report",
    requires=(
        context_value(K.PROTOTYPE_STRUCTURE, PrototypeStructure),
        context_value(K.COLOR_CATALOG, ColorCatalog),
    ),
    produces=(context_value(K.DERIVED_CONTRAST_REPORT, ContrastReport),),
)


def _resolve_color_source(
    prototype_structure: PrototypeStructure,
    *,
    element: Element,
    color_entry: Color | None,
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
    *,
    color_entry: Color | None,
    source_element: Element | None,
    source_property: Property | None,
) -> ContrastColorReference:
    return ContrastColorReference(
        css=color_entry.value if color_entry is not None else "",
        hex_value=color_entry.hex_value if color_entry is not None else "",
        alpha=color_entry.alpha if color_entry is not None else 0.0,
        color_id=color_entry.color_id if color_entry is not None else None,
        element_id=source_element.node_id if source_element is not None else None,
        style_id=source_property.style_id if source_property is not None else None,
        declaration_id=source_property.declaration_id if source_property is not None else None,
        property_name=source_property.name if source_property is not None else None,
        declared_property=source_property.declared_property if source_property is not None else None,
    )


def _property_value(element: Element, property_name: str) -> str:
    property_model = next(
        (item for item in element.properties if item.name == property_name),
        None,
    )
    return str(property_model.value or "").strip() if property_model is not None else ""


def _font_size_px(element: Element) -> float:
    value = _property_value(element, "font-size").lower()
    if value.endswith("px"):
        value = value[:-2]
    try:
        return round(float(value), 4)
    except ValueError:
        return 0.0


def _font_weight(element: Element) -> int:
    value = _property_value(element, "font-weight").lower()
    if value == "bold":
        return 700
    try:
        return int(float(value))
    except ValueError:
        return 400


def _contrast_ratio(foreground: Color, background: Color) -> float | None:
    try:
        foreground_value: Any = foreground.value
        if foreground.alpha < 1.0:
            foreground_value = color_registry.composite_over(foreground.value, background.value)
        return round(float(color_registry.contrast_ratio(foreground_value, background.value)), 4)
    except Exception:
        return None


def _text_sample(element: Element) -> str:
    return str(element.text or "").strip()[:160]


def _bounds(element: Element) -> dict[str, float]:
    return {
        "x": round(element.x, 4),
        "y": round(element.y, 4),
        "width": round(element.width, 4),
        "height": round(element.height, 4),
    }


def _build_report(
    prototype_structure: PrototypeStructure,
    colors_inventory: ColorCatalog,
) -> ContrastReport:
    issues: list[ContrastIssue] = []

    for element in prototype_structure.visible_nodes():
        text_sample = _text_sample(element)
        if not text_sample:
            continue

        foreground_entry = prototype_structure.effective_color_of(
            element.node_id,
            colors_inventory,
        )
        background_entry = prototype_structure.effective_background_of(
            element.node_id,
            colors_inventory,
        )
        if foreground_entry is None or background_entry is None:
            continue

        ratio = _contrast_ratio(foreground_entry, background_entry)
        if ratio is None:
            continue

        font_size_px = _font_size_px(element)
        font_weight = _font_weight(element)
        large_text = font_size_px >= 24.0 or (font_size_px >= 18.667 and font_weight >= 700)
        required_ratio = 3.0 if large_text else 4.5
        if ratio >= required_ratio:
            continue

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
        if background_source_element is None:
            background_source_element = prototype_structure.surface_container_of(element.node_id)

        issues.append(
            ContrastIssue(
                issue_id=f"contrast-{len(issues) + 1}",
                element_id=element.node_id,
                selector=element.selector or element.xpath or element.node_id,
                tag_name=element.tag_name,
                text_sample=text_sample,
                contrast_ratio=ratio,
                required_ratio=required_ratio,
                is_large_text=large_text,
                font_size_px=font_size_px,
                font_weight=font_weight,
                bounds=_bounds(element),
                foreground=_build_color_reference(
                    color_entry=foreground_entry,
                    source_element=foreground_source_element,
                    source_property=foreground_property,
                ),
                background=_build_color_reference(
                    color_entry=background_entry,
                    source_element=background_source_element,
                    source_property=background_property,
                ),
                background_validation=ContrastBackgroundValidation.MODEL,
            )
        )

    issues.sort(key=lambda issue: (issue.contrast_ratio, issue.selector, issue.issue_id))
    return ContrastReport(issues=tuple(issues))


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has(K.DERIVED_CONTRAST_REPORT):
        return context

    context.trace.add_stage_event(CONTRACT.name, "start")
    report = _build_report(
        context.get(K.PROTOTYPE_STRUCTURE),
        context.get(K.COLOR_CATALOG),
    )
    context.set(K.DERIVED_CONTRAST_REPORT, report)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "contrast_issue_count": len(report),
            "linked_issue_count": sum(1 for issue in report if issue.element_id is not None),
        },
    )
    return context
