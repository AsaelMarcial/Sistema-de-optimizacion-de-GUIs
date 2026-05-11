from __future__ import annotations

from typing import Any, Iterable

from engine.adapters.color_service import color_registry
from engine.domain.models.color import Color, ColorCatalog
from engine.domain.models.element import Element, Property
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.style import StyleCatalog

def build_css_overview_from_models(
    prototype_structure: PrototypeStructure,
    style_catalog: StyleCatalog,
    colors_inventory: ColorCatalog,
) -> dict[str, Any]:
    elements = tuple(
        _element_payload(prototype_structure, element, colors_inventory)
        for element in prototype_structure
        if not element.is_text_node
    )
    stylesheets = _build_stylesheets(style_catalog)
    unused_declarations = _build_unused_declarations(style_catalog)
    return build_css_overview(
        {
            "metadata": dict(getattr(prototype_structure, "document", {}) or {}),
            "stylesheets": stylesheets,
            "unused_declarations": unused_declarations,
            "elements": elements,
        }
    )


def build_css_overview(payload: dict[str, Any]) -> dict[str, Any]:
    elements = tuple(payload.get("elements") or ())
    visible_elements = tuple(element for element in elements if element.get("is_visible"))
    contrast_issues = _build_contrast_issues(visible_elements)
    stylesheets = tuple(payload.get("stylesheets") or ())
    media_queries: list[dict[str, Any]] = []
    unused_declarations = {
        "count": len(payload.get("unused_declarations") or ()),
        "entries": list(payload.get("unused_declarations") or ()),
    }
    colors = {
        "text": _collect_color_entries(visible_elements, "text"),
        "background": _collect_color_entries(visible_elements, "background"),
        "border": _collect_border_color_entries(visible_elements),
        "fill": _collect_color_entries(visible_elements, "fill"),
        "stroke": _collect_color_entries(visible_elements, "stroke"),
    }
    typography = _build_typography(visible_elements)
    summary = {
        "element_count": len(elements),
        "visible_element_count": len(visible_elements),
        "text_element_count": sum(1 for element in visible_elements if str(element.get("text_sample") or "").strip()),
        "inline_style_count": sum(1 for element in elements if element.get("inline_style")),
        "stylesheet_count": len(stylesheets),
        "external_stylesheet_count": sum(1 for sheet in stylesheets if sheet.get("href")),
        "inline_stylesheet_count": sum(1 for sheet in stylesheets if not sheet.get("href")),
        "media_query_count": len(media_queries),
        "contrast_issue_count": len(contrast_issues),
        "unused_declaration_count": unused_declarations["count"],
    }

    return {
        "metadata": {
            **dict(payload.get("metadata") or {}),
            "generator": "css_overview_adapter",
        },
        "summary": summary,
        "stylesheets": {
            "entries": list(stylesheets),
        },
        "colors": colors,
        "typography": typography,
        "media_queries": media_queries,
        "contrast_issues": contrast_issues,
        "unused_declarations": unused_declarations,
        "unsupported_sections": [],
    }


def _element_payload(
    prototype_structure: PrototypeStructure,
    element: Element,
    colors_inventory: ColorCatalog,
) -> dict[str, Any]:
    properties_by_name = {property_model.name: property_model for property_model in element.properties}
    foreground = prototype_structure.effective_color_of(element.node_id, colors_inventory)
    background = prototype_structure.effective_background_of(element.node_id, colors_inventory)
    text_value = str(element.text or "").strip()
    return {
        "node_id": element.node_id,
        "tag_name": element.tag_name,
        "selector": element.selector or element.xpath or element.node_id,
        "id": element.html_id,
        "class_list": list(element.class_names),
        "text_sample": text_value[:160],
        "is_visible": element.is_visible,
        "inline_style": element.attributes.get("style") if element.attributes else None,
        "colors": {
            "text": _color_css(foreground),
            "background": _color_css(background),
            "border_top": _property_color_css(properties_by_name, colors_inventory, "border-top-color", "border-color"),
            "border_right": _property_color_css(properties_by_name, colors_inventory, "border-right-color", "border-color"),
            "border_bottom": _property_color_css(properties_by_name, colors_inventory, "border-bottom-color", "border-color"),
            "border_left": _property_color_css(properties_by_name, colors_inventory, "border-left-color", "border-color"),
            "fill": _property_color_css(properties_by_name, colors_inventory, "fill"),
            "stroke": _property_color_css(properties_by_name, colors_inventory, "stroke"),
            "effective_background_stack": [_color_css(background)] if background is not None else [],
        },
        "typography": {
            "font_family": _property_value(properties_by_name, "font-family"),
            "font_size_px": _font_size_px(_property_value(properties_by_name, "font-size")),
            "font_weight": _font_weight(_property_value(properties_by_name, "font-weight")),
            "line_height": _property_value(properties_by_name, "line-height") or "normal",
        },
        "bounds": {
            "x": round(element.x),
            "y": round(element.y),
            "width": round(element.width),
            "height": round(element.height),
        },
    }


def _build_stylesheets(style_catalog: StyleCatalog) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for style_rule in style_catalog:
        source = style_rule.source_url or "inline"
        bucket = buckets.setdefault(
            source,
            {
                "href": style_rule.source_url,
                "is_inline": style_rule.source_url is None,
                "rules_count": 0,
            },
        )
        bucket["rules_count"] += 1
    return sorted(buckets.values(), key=lambda item: (not item["is_inline"], item["href"] or ""))


def _build_unused_declarations(style_catalog: StyleCatalog) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for style_rule in style_catalog:
        if not style_rule.selectors:
            continue
        if style_rule.used:
            continue
        selector = style_rule.selector_text or ""
        for declaration in style_rule.declarations:
            entries.append(
                {
                    "selector": selector,
                    "tag_name": "",
                    "property": str(declaration.name),
                    "value": declaration.value_text,
                    "reason": "rule has no linked selector usage",
                    "source_kind": style_rule.source_kind.value,
                    "source": style_rule.source_url,
                    "rule_selector": style_rule.selector_text,
                }
            )
    entries.sort(key=lambda item: (item["selector"], item["property"], item["source_kind"]))
    return entries


def _property_value(properties_by_name: dict[str, Property], name: str) -> str:
    property_model = properties_by_name.get(name)
    return str(property_model.value or "").strip() if property_model is not None else ""


def _property_color_css(
    properties_by_name: dict[str, Property],
    colors_inventory: ColorCatalog,
    *names: str,
) -> str | None:
    for name in names:
        property_model = properties_by_name.get(name)
        if property_model is None:
            continue
        color_entry = _property_color(property_model, colors_inventory)
        if color_entry is not None:
            return _color_css(color_entry)
        normalized = _normalize_color(property_model.value)
        if normalized is not None:
            return normalized["css"]
    return None


def _property_color(property_model: Property, colors_inventory: ColorCatalog) -> Color | None:
    if property_model.color_id:
        entry = colors_inventory.entry_by_id(property_model.color_id)
        if entry is not None:
            return entry
    return colors_inventory.entry_by_value(property_model.value)


def _color_css(color_entry: Color | None) -> str | None:
    return color_entry.value if color_entry is not None else None


def _font_size_px(value: str) -> float:
    normalized = str(value or "").strip().lower()
    if normalized.endswith("px"):
        normalized = normalized[:-2]
    try:
        return round(float(normalized), 4)
    except ValueError:
        return 0.0


def _font_weight(value: str) -> int:
    normalized = str(value or "").strip().lower()
    if normalized == "bold":
        return 700
    try:
        return int(float(normalized))
    except ValueError:
        return 400


def _collect_color_entries(elements: tuple[dict[str, Any], ...], color_key: str) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, float], dict[str, Any]] = {}
    for element in elements:
        colors = element.get("colors") or {}
        normalized = _normalize_color(colors.get(color_key))
        if normalized is None:
            continue
        bucket = buckets.setdefault(
            (normalized["hex"], normalized["alpha"]),
            {
                **normalized,
                "count": 0,
                "node_ids": [],
                "sample_selectors": [],
            },
        )
        bucket["count"] += 1
        _append_unique_value(bucket["node_ids"], element.get("node_id"))
        _append_sample_selector(bucket["sample_selectors"], element.get("selector"))
    return _sorted_entries(buckets.values())


def _collect_border_color_entries(elements: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, float], dict[str, Any]] = {}
    for element in elements:
        colors = element.get("colors") or {}
        for border_key in ("border_top", "border_right", "border_bottom", "border_left"):
            normalized = _normalize_color(colors.get(border_key))
            if normalized is None:
                continue
            bucket = buckets.setdefault(
                (normalized["hex"], normalized["alpha"]),
                {
                    **normalized,
                    "count": 0,
                    "node_ids": [],
                    "sample_selectors": [],
                },
            )
            bucket["count"] += 1
            _append_unique_value(bucket["node_ids"], element.get("node_id"))
            _append_sample_selector(bucket["sample_selectors"], element.get("selector"))
    return _sorted_entries(buckets.values())


def _build_typography(elements: tuple[dict[str, Any], ...]) -> dict[str, list[dict[str, Any]]]:
    families: dict[str, dict[str, Any]] = {}
    styles: dict[tuple[str, float, int, str], dict[str, Any]] = {}
    for element in elements:
        typography = element.get("typography") or {}
        font_family = str(typography.get("font_family") or "").strip()
        if not font_family:
            continue
        family_bucket = families.setdefault(
            font_family,
            {
                "font_family": font_family,
                "count": 0,
                "sample_selectors": [],
            },
        )
        family_bucket["count"] += 1
        _append_sample_selector(family_bucket["sample_selectors"], element.get("selector"))
        font_size_px = round(float(typography.get("font_size_px") or 0.0), 4)
        font_weight = int(typography.get("font_weight") or 400)
        line_height = str(typography.get("line_height") or "").strip() or "normal"
        style_bucket = styles.setdefault(
            (font_family, font_size_px, font_weight, line_height),
            {
                "font_family": font_family,
                "font_size_px": font_size_px,
                "font_weight": font_weight,
                "line_height": line_height,
                "count": 0,
                "sample_selectors": [],
            },
        )
        style_bucket["count"] += 1
        _append_sample_selector(style_bucket["sample_selectors"], element.get("selector"))
    return {
        "font_families": _sorted_entries(families.values(), "font_family"),
        "text_styles": _sorted_entries(styles.values(), "font_family", "font_size_px", "font_weight", "line_height"),
    }


def _build_contrast_issues(elements: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for element in elements:
        text_sample = str(element.get("text_sample") or "").strip()
        if not text_sample:
            continue
        colors = element.get("colors") or {}
        foreground = _normalize_color(colors.get("text"))
        background = _resolve_background_color(colors.get("effective_background_stack") or [])
        if foreground is None or background is None:
            continue
        try:
            effective_foreground: Any = foreground["color"]
            if foreground["alpha"] < 1.0:
                effective_foreground = color_registry.composite_over(
                    effective_foreground,
                    background["color"],
                )
            ratio = round(float(color_registry.contrast_ratio(effective_foreground, background["color"])), 4)
        except Exception:
            continue
        typography = element.get("typography") or {}
        font_size_px = round(float(typography.get("font_size_px") or 0.0), 4)
        font_weight = int(typography.get("font_weight") or 400)
        large_text = font_size_px >= 24.0 or (font_size_px >= 18.667 and font_weight >= 700)
        required_ratio = 3.0 if large_text else 4.5
        if ratio >= required_ratio:
            continue
        issues.append(
            {
                "node_id": element.get("node_id") or None,
                "selector": element.get("selector") or "",
                "tag_name": element.get("tag_name") or "",
                "text_sample": text_sample,
                "contrast_ratio": ratio,
                "required_ratio": required_ratio,
                "font_size_px": font_size_px,
                "font_weight": font_weight,
                "foreground": {
                    "css": foreground["css"],
                    "hex": foreground["hex"],
                    "alpha": foreground["alpha"],
                },
                "background": {
                    "css": background["css"],
                    "hex": background["hex"],
                    "alpha": background["alpha"],
                },
                **({"is_large_text": True} if large_text else {}),
                **({"bounds": dict(element.get("bounds") or {})} if element.get("bounds") else {}),
            }
        )
    issues.sort(key=lambda item: (item["contrast_ratio"], item["selector"]))
    return issues


def _resolve_background_color(stack: Iterable[Any]) -> dict[str, Any] | None:
    composite: Any = "#ffffff"
    found_visible_layer = False
    for layer in reversed(tuple(stack)):
        normalized = _normalize_color(layer)
        if normalized is None:
            continue
        found_visible_layer = True
        composite = color_registry.composite_over(normalized["color"], composite)
    if not found_visible_layer:
        composite = "#ffffff"
    return _normalize_color(composite)


def _normalize_color(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, str):
        raw_value = value.strip()
        if not raw_value or raw_value.lower() in {"transparent", "none", "currentcolor", "inherit", "initial"}:
            return None
        color_value: Any = raw_value
    else:
        color_value = value
    try:
        red, green, blue, alpha = color_registry.format_color(color_value, "rgba")
        if alpha <= 0:
            return None
        css_value = (
            f"rgba({red}, {green}, {blue}, {round(alpha, 4)})"
            if alpha < 1.0
            else f"rgb({red}, {green}, {blue})"
        )
        return {
            "css": css_value,
            "hex": color_registry.format_color(color_value, "hex"),
            "alpha": round(alpha, 4),
            "rgba": [red, green, blue, round(alpha, 4)],
            "color": color_value,
        }
    except Exception:
        return None


def _append_sample_selector(target: list[str], selector: Any) -> None:
    normalized = str(selector or "").strip()
    if not normalized or normalized in target or len(target) >= 5:
        return
    target.append(normalized)


def _append_unique_value(target: list[str], value: Any) -> None:
    normalized = str(value or "").strip()
    if not normalized or normalized in target:
        return
    target.append(normalized)


def _sorted_entries(entries: Any, *extra_sort_keys: str) -> list[dict[str, Any]]:
    sort_keys = extra_sort_keys or ("hex",)
    return sorted(
        (dict(entry) for entry in entries),
        key=lambda item: tuple([-int(item.get("count") or 0), *[item.get(key) for key in sort_keys]]),
    )
