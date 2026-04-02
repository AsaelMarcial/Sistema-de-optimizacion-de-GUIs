from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from engine.adapters.color_service import color_registry
from engine.domain.data.css_properties import (
    CSS_PROPERTY_SHORTHANDS,
    get_css_property,
)
from engine.domain.models.color import ColorInventoryModel
from engine.domain.models.style import (
    ComputedStyleValueModel,
    StyleInventoryEntry,
    StyleInventoryModel,
)

_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_FUNCTION_COLOR_RE = re.compile(r"(?:rgba?|hsla?)\([^)]+\)", re.IGNORECASE)
_IMPORTANT_SUFFIX_RE = re.compile(r"\s*!important\s*$", re.IGNORECASE)
_RESOLVE_VALUE_RE = re.compile(
    r"\b(?:var|calc|min|max|clamp|attr|color-mix)\(|currentColor\b",
    re.IGNORECASE,
)

_PURE_COLOR_PROPERTIES = {
    "accent-color",
    "background-color",
    "border-block-end-color",
    "border-block-start-color",
    "border-bottom-color",
    "border-color",
    "border-inline-start-color",
    "border-left-color",
    "border-right-color",
    "border-top-color",
    "caret-color",
    "color",
    "column-rule-color",
    "fill",
    "flood-color",
    "lighting-color",
    "outline-color",
    "stop-color",
    "stroke",
    "text-decoration-color",
    "text-emphasis-color",
}

_COLOR_VALUE_PROPERTIES = _PURE_COLOR_PROPERTIES | {
    "background",
    "border",
    "caret",
    "column-rule",
    "outline",
    "text-decoration",
    "text-emphasis",
}

_INHERITED_SCOPE_PROPERTIES = {
    "accent-color",
    "caret-color",
    "color",
    "fill",
    "fill-opacity",
    "stroke",
    "stroke-opacity",
    "visibility",
}


def register_stylesheet_headers(cdp: Any) -> dict[str, dict[str, Any]]:
    headers: dict[str, dict[str, Any]] = {}
    sheet_order = 0

    def _on_style_added(params: dict[str, Any]) -> None:
        nonlocal sheet_order
        header = (params or {}).get("header", {})
        style_sheet_id = header.get("styleSheetId")
        if not style_sheet_id:
            return
        sheet_order += 1
        headers[style_sheet_id] = {
            "style_sheet_id": style_sheet_id,
            "origin": _normalize_cascade_origin(header.get("origin")),
            "source_url": header.get("sourceURL") or None,
            "title": header.get("title") or None,
            "is_inline": bool(header.get("isInline", False)),
            "sheet_order": sheet_order,
        }

    cdp.on("CSS.styleSheetAdded", _on_style_added)
    return headers


def _normalize_css_value(property_name: str, value: str) -> str:
    if property_name in _PURE_COLOR_PROPERTIES:
        return _normalize_color_token(value)
    return str(value).strip()


def _normalize_color_token(value: str) -> str:
    return color_registry.normalize_css_color_token(value)


def _extract_declarations(style_obj: dict[str, Any]) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, bool, bool]] = set()
    raw_properties = style_obj.get("cssProperties", []) or []
    authored_properties = [
        prop
        for prop in raw_properties
        if isinstance(prop, dict) and (prop.get("text") or prop.get("range"))
    ]
    properties = authored_properties or raw_properties

    for index, prop in enumerate(properties):
        name = prop.get("name")
        value = prop.get("value")
        property_spec = get_css_property(name)
        if not name or value in (None, "") or property_spec is None:
            continue

        canonical_name = property_spec.value
        raw_value = _strip_important_annotation(str(value))
        normalized_value = _normalize_css_value(canonical_name, raw_value)
        signature = (
            canonical_name,
            normalized_value,
            bool(prop.get("important", False)),
            bool(prop.get("implicit", False)),
        )
        if signature in seen:
            continue

        seen.add(signature)
        declarations.append(
            {
                "name": canonical_name,
                "value": normalized_value,
                "important": signature[2],
                "implicit": signature[3],
                "declaration_order": index,
                "longhand_properties": tuple(prop.get("longhandProperties") or ()),
            }
        )

    return declarations


def _strip_important_annotation(value: str) -> str:
    return _IMPORTANT_SUFFIX_RE.sub("", value).strip()


def _sanitize_declarations(declarations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": item["name"],
            "value": item["value"],
            "important": item["important"],
            "implicit": item["implicit"],
        }
        for item in declarations
    ]


def _normalize_source_range(raw_range: dict[str, Any] | None) -> dict[str, int] | None:
    if not raw_range:
        return None

    start_line = raw_range.get("startLine")
    start_column = raw_range.get("startColumn")
    end_line = raw_range.get("endLine")
    end_column = raw_range.get("endColumn")
    if not all(isinstance(value, int) for value in (start_line, start_column, end_line, end_column)):
        return None

    return {
        "start_line": start_line,
        "start_column": start_column,
        "end_line": end_line,
        "end_column": end_column,
    }


def _specificity_tuple(raw_specificity: Any) -> tuple[int, int, int] | None:
    if raw_specificity is None:
        return None

    if isinstance(raw_specificity, dict):
        a_value = raw_specificity.get("a")
        b_value = raw_specificity.get("b")
        c_value = raw_specificity.get("c")
        if all(isinstance(value, int) for value in (a_value, b_value, c_value)):
            return (a_value, b_value, c_value)

    if isinstance(raw_specificity, (list, tuple)) and len(raw_specificity) >= 3:
        return tuple(int(value) for value in raw_specificity[:3])

    if isinstance(raw_specificity, str):
        parts = [part.strip() for part in raw_specificity.split(",")]
        if len(parts) >= 3 and all(part.isdigit() for part in parts[:3]):
            return tuple(int(part) for part in parts[:3])

    return None


def _serialize_specificity(raw_specificity: tuple[int, int, int] | None) -> dict[str, int] | None:
    if raw_specificity is None:
        return None
    return {
        "a": raw_specificity[0],
        "b": raw_specificity[1],
        "c": raw_specificity[2],
    }


def _extract_matching_selector_metadata(
    rule_entry: dict[str, Any],
) -> tuple[int | None, tuple[int, int, int] | None, dict[str, int] | None]:
    matching_indexes = [index for index in rule_entry.get("matchingSelectors", []) or [] if isinstance(index, int)]
    selector_list = ((rule_entry.get("rule") or {}).get("selectorList") or {}).get("selectors") or []
    if not selector_list or not matching_indexes:
        return None, None, None

    best_index: int | None = None
    best_specificity: tuple[int, int, int] | None = None
    best_range: dict[str, int] | None = None

    for index in matching_indexes:
        if index < 0 or index >= len(selector_list):
            continue
        selector_payload = selector_list[index] or {}
        specificity = _specificity_tuple(selector_payload.get("specificity"))
        selector_range = _normalize_source_range(selector_payload.get("range"))
        if best_index is None or (
            specificity is not None and (best_specificity is None or specificity > best_specificity)
        ):
            best_index = index
            best_specificity = specificity
            best_range = selector_range

    return best_index, best_specificity, best_range


def _build_layer_order_map(payload: Any) -> dict[str, int]:
    layer_orders: dict[str, int] = {}
    layer_index = 0

    def _walk(node: Any) -> None:
        nonlocal layer_index
        if isinstance(node, dict):
            name = node.get("name") or node.get("text")
            if isinstance(name, str) and name:
                layer_index += 1
                layer_orders.setdefault(name, layer_index)
            for key in ("children", "layers", "subLayers"):
                for child in node.get(key, []) or []:
                    _walk(child)
        elif isinstance(node, list):
            for child in node:
                _walk(child)

    _walk(payload)
    return layer_orders


def _fetch_layer_orders(cdp: Any, frontend_node_id: int) -> dict[str, int]:
    try:
        payload = cdp.send("CSS.getLayersForNode", {"nodeId": frontend_node_id})
    except Exception:
        return {}
    return _build_layer_order_map(payload)


def _extract_layer_metadata(rule: dict[str, Any], layer_orders: dict[str, int]) -> tuple[str | None, int | None]:
    raw_layers = rule.get("layers") or []
    layer_names = [
        layer.get("text") or layer.get("name")
        for layer in raw_layers
        if isinstance(layer, dict) and (layer.get("text") or layer.get("name"))
    ]
    if not layer_names:
        return None, None

    normalized_name = " > ".join(reversed(layer_names))
    candidate_orders = [layer_orders[name] for name in layer_names if name in layer_orders]
    return normalized_name, (max(candidate_orders) if candidate_orders else None)


def _style_kind(
    *,
    origin: str | None,
    inherited_from_element_id: str | None,
    inline: bool = False,
    attributes: bool = False,
    source_url: str | None = None,
) -> str:
    if inherited_from_element_id:
        return "inherited"
    if origin == "user-agent":
        return "user-agent"
    if inline or attributes:
        return "inline"
    if source_url:
        return "external"
    return "embedded"


def _normalize_cascade_origin(origin: str | None) -> str:
    normalized = str(origin or "").strip().lower()
    if normalized == "user-agent":
        return "user-agent"
    if normalized == "user":
        return "user"
    return "author"


def _style_sort_key(
    stylesheet_header: dict[str, Any] | None,
    source_range: dict[str, int] | None,
    declaration_seed: int,
) -> tuple[int, int, int, int]:
    sheet_order = int((stylesheet_header or {}).get("sheet_order") or 0)
    start_line = int((source_range or {}).get("start_line") or 0)
    start_column = int((source_range or {}).get("start_column") or 0)
    return (sheet_order, start_line, start_column, declaration_seed)


def _build_inline_entry(
    style_obj: dict[str, Any],
    stylesheet_headers: dict[str, dict[str, Any]],
    *,
    kind: str,
    inherited_from_element_id: str | None,
    resolution_frontend_node_id: int,
    source_computed_styles: dict[str, str],
    source_parent_computed_styles: dict[str, str],
    declaration_seed: int,
) -> dict[str, Any] | None:
    declarations = _extract_declarations(style_obj)
    if not declarations:
        return None

    style_sheet_id = style_obj.get("styleSheetId")
    stylesheet_header = stylesheet_headers.get(style_sheet_id)
    source_range = _normalize_source_range(style_obj.get("range"))
    style_kind = _style_kind(
        origin="author",
        inherited_from_element_id=inherited_from_element_id,
        inline=kind == "inline",
        attributes=kind == "attributes",
        source_url=(stylesheet_header or {}).get("source_url"),
    )

    return {
        "kind": style_kind,
        "origin": "author",
        "style_sheet_id": style_sheet_id,
        "selector_text": None,
        "declarations": declarations,
        "matching_selector_index": None,
        "specificity": None,
        "source_range": source_range,
        "layer_name": None,
        "layer_order": None,
        "source_url": (stylesheet_header or {}).get("source_url"),
        "_sort_key": _style_sort_key(stylesheet_header, source_range, declaration_seed),
        "_resolution_frontend_node_id": resolution_frontend_node_id,
        "_source_computed_styles": source_computed_styles,
        "_source_parent_computed_styles": source_parent_computed_styles,
        "_inherited_from_element_id": inherited_from_element_id,
    }


def _build_rule_entry(
    rule_entry: dict[str, Any],
    stylesheet_headers: dict[str, dict[str, Any]],
    layer_orders: dict[str, int],
    *,
    inherited_from_element_id: str | None,
    resolution_frontend_node_id: int,
    source_computed_styles: dict[str, str],
    source_parent_computed_styles: dict[str, str],
    declaration_seed: int,
) -> dict[str, Any] | None:
    rule = rule_entry.get("rule", {})
    style = rule.get("style", {})
    declarations = _extract_declarations(style)
    if not declarations:
        return None

    style_sheet_id = style.get("styleSheetId")
    stylesheet_header = stylesheet_headers.get(style_sheet_id)
    matching_selector_index, specificity, selector_range = _extract_matching_selector_metadata(rule_entry)
    source_range = _normalize_source_range(style.get("range")) or selector_range
    selector_text = ((rule.get("selectorList") or {}).get("text")) or None
    layer_name, layer_order = _extract_layer_metadata(rule, layer_orders)
    origin = _normalize_cascade_origin(rule.get("origin"))
    source_url = (stylesheet_header or {}).get("source_url")

    return {
        "kind": _style_kind(
            origin=origin,
            inherited_from_element_id=inherited_from_element_id,
            source_url=source_url,
        ),
        "origin": origin,
        "style_sheet_id": style_sheet_id,
        "selector_text": selector_text,
        "declarations": declarations,
        "matching_selector_index": matching_selector_index,
        "specificity": specificity,
        "source_range": source_range,
        "layer_name": layer_name,
        "layer_order": layer_order,
        "source_url": source_url,
        "_sort_key": _style_sort_key(stylesheet_header, source_range, declaration_seed),
        "_resolution_frontend_node_id": resolution_frontend_node_id,
        "_source_computed_styles": source_computed_styles,
        "_source_parent_computed_styles": source_parent_computed_styles,
        "_inherited_from_element_id": inherited_from_element_id,
    }


def _inventory_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    return (
        entry["kind"],
        entry["origin"],
        entry["style_sheet_id"],
        entry["selector_text"],
        tuple(sorted((entry["source_range"] or {}).items())),
        entry["layer_name"],
        entry["layer_order"],
        entry["source_url"],
        tuple(
            (
                declaration["name"],
                declaration["value"],
                declaration["important"],
                declaration["implicit"],
            )
            for declaration in entry["declarations"]
        ),
    )


def _register_style_inventory_entry(
    aggregate: dict[tuple[Any, ...], dict[str, Any]],
    *,
    entry: dict[str, Any],
    node_id: str,
) -> tuple[Any, ...]:
    key = _inventory_key(entry)
    if key not in aggregate:
        aggregate[key] = {
            "kind": entry["kind"],
            "origin": entry["origin"],
            "style_sheet_id": entry["style_sheet_id"],
            "selector_text": entry["selector_text"],
            "declarations": _sanitize_declarations(entry["declarations"]),
            "source_range": entry["source_range"],
            "layer_name": entry["layer_name"],
            "layer_order": entry["layer_order"],
            "source_url": entry["source_url"],
            "node_ids": set(),
            "usage_count": 0,
            "_sort_key": entry["_sort_key"],
        }

    aggregate[key]["node_ids"].add(node_id)
    aggregate[key]["usage_count"] += 1
    return key


def _build_styles_inventory(
    aggregate: dict[tuple[Any, ...], dict[str, Any]],
    ) -> tuple[StyleInventoryModel, dict[tuple[Any, ...], str]]:
    return StyleInventoryModel.build_from_aggregate(aggregate)


def _computed_style_map(raw_node: dict[str, Any]) -> dict[str, str]:
    computed: dict[str, str] = {}
    for raw_value in raw_node.get("styles", {}).get("computed", []):
        if ":" not in raw_value:
            continue
        name, value = raw_value.split(":", 1)
        computed[name] = _normalize_css_value(name, value)
    return computed


def _origin_family(candidate: dict[str, Any]) -> str:
    if candidate["kind"] in {"inline", "embedded", "external", "inherited"}:
        return "author"
    if candidate.get("origin") == "user":
        return "user"
    if candidate.get("origin") == "user-agent" or candidate["kind"] == "user-agent":
        return "user-agent"
    return "author"


def _inline_specificity(candidate: dict[str, Any]) -> tuple[int, int, int, int]:
    if candidate["kind"] == "inline":
        return (1, 0, 0, 0)
    specificity = candidate.get("specificity")
    if isinstance(specificity, tuple):
        return (0, specificity[0], specificity[1], specificity[2])
    return (0, 0, 0, 0)


def _layer_priority(candidate: dict[str, Any]) -> tuple[int, int]:
    layer_order = candidate.get("layer_order")
    inline_bonus = 2 if candidate["kind"] == "inline" else 0

    if candidate["important"]:
        if candidate["kind"] == "inline":
            return (inline_bonus, 0)
        if layer_order is None:
            return (0, 0)
        return (1, -int(layer_order))

    if candidate["kind"] == "inline":
        return (inline_bonus, 0)
    if layer_order is None:
        return (1, 0)
    return (0, int(layer_order))


def _cascade_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    important = 1 if candidate["important"] else 0
    origin_family = _origin_family(candidate)
    if candidate["important"]:
        origin_rank = {
            "author": 0,
            "user": 1,
            "user-agent": 2,
        }.get(origin_family, 0)
    else:
        origin_rank = {
            "user-agent": 0,
            "user": 1,
            "author": 2,
        }.get(origin_family, 2)

    return (
        important,
        origin_rank,
        _layer_priority(candidate),
        _inline_specificity(candidate),
        candidate["source_order"],
    )


def _extract_palette_colors(property_name: str, value: str) -> list[str]:
    if property_name not in _COLOR_VALUE_PROPERTIES:
        return []

    if property_name in _PURE_COLOR_PROPERTIES:
        normalized = _normalize_color_token(value)
        return [] if not normalized or normalized == "transparent" else [normalized]

    colors = []
    for token in _HEX_COLOR_RE.findall(value):
        normalized = _normalize_color_token(token)
        if normalized and normalized != "transparent" and normalized not in colors:
            colors.append(normalized)

    for token in _FUNCTION_COLOR_RE.findall(value):
        normalized = _normalize_color_token(token)
        if normalized and normalized != "transparent" and normalized not in colors:
            colors.append(normalized)

    return colors


def _resolve_palette_targets(property_name: str, computed_styles: dict[str, str]) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if property_name in _COLOR_VALUE_PROPERTIES and property_name in computed_styles:
        targets.append((property_name, computed_styles[property_name]))

    return targets


def _collect_palette_usage(
    palette_usage: dict[str, dict[str, Any]],
    raw_node: dict[str, Any],
    computed_styles: dict[str, str],
    direct_property_names: set[str],
) -> None:
    node_id = raw_node["node_id"]
    tag_name = raw_node["identity"]["tag"]
    seen_usages: set[tuple[str, str]] = set()

    for property_name in sorted(direct_property_names):
        for resolved_property, resolved_value in _resolve_palette_targets(property_name, computed_styles):
            for color in _extract_palette_colors(resolved_property, resolved_value):
                if color == "transparent":
                    continue
                signature = (resolved_property, color)
                if signature in seen_usages:
                    continue
                seen_usages.add(signature)

                entry = palette_usage.setdefault(
                    color,
                    {
                        "value": color,
                        "node_ids": set(),
                        "usage": defaultdict(set),
                    },
                )
                entry["node_ids"].add(node_id)
                entry["usage"][(tag_name, resolved_property)].add(node_id)


def _normalize_palette(palette_usage: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    palette: list[dict[str, Any]] = []
    for index, value in enumerate(sorted(palette_usage), start=1):
        entry = palette_usage[value]
        usage = [
            {
                "tag": tag_name,
                "property": property_name,
                "count": len(node_ids),
            }
            for (tag_name, property_name), node_ids in sorted(
                entry["usage"].items(),
                key=lambda item: (item[0][0], item[0][1]),
            )
        ]
        palette.append(
            {
                "color_id": f"color-{index}",
                "value": value,
                "usage_count": len(entry["node_ids"]),
                "usage": usage,
            }
        )
    return palette


def _normalize_background_colors(background_payload: dict[str, Any] | None) -> tuple[list[str] | None, str | None]:
    if not background_payload:
        return None, None

    raw_colors = background_payload.get("backgroundColors") or []
    normalized_colors = []
    for color in raw_colors:
        normalized = _normalize_color_token(str(color))
        if normalized not in normalized_colors:
            normalized_colors.append(normalized)

    return normalized_colors or None, (normalized_colors[0] if normalized_colors else None)


def _should_attempt_resolve(value: str) -> bool:
    return bool(value) and bool(_RESOLVE_VALUE_RE.search(value))


def _extract_resolved_values(payload: dict[str, Any]) -> list[str]:
    for key in ("results", "resolvedValues", "values"):
        values = payload.get(key)
        if isinstance(values, list):
            extracted = []
            for item in values:
                if isinstance(item, dict):
                    extracted.append(
                        item.get("value")
                        or item.get("text")
                        or item.get("resolvedValue")
                        or ""
                    )
                elif isinstance(item, str):
                    extracted.append(item)
            return extracted
    return []


def _resolve_css_value(
    cdp: Any,
    frontend_node_id: int,
    property_name: str,
    value: str,
    cache: dict[tuple[int, str, str], str | None],
) -> str | None:
    cache_key = (frontend_node_id, property_name, value)
    if cache_key in cache:
        return cache[cache_key]

    try:
        payload = cdp.send(
            "CSS.resolveValues",
            {
                "nodeId": frontend_node_id,
                "propertyName": property_name,
                "values": [value],
            },
        )
    except Exception:
        cache[cache_key] = None
        return None

    resolved_values = _extract_resolved_values(payload)
    resolved = resolved_values[0] if resolved_values else None
    cache[cache_key] = resolved
    return resolved


def _expand_declaration_targets(
    cdp: Any,
    declaration: dict[str, Any],
    cache: dict[tuple[str, str], list[tuple[str, str]]],
) -> list[tuple[str, str]]:
    property_name = declaration["name"]
    property_value = declaration["value"]
    cache_key = (property_name, property_value)
    if cache_key in cache:
        return cache[cache_key]

    expanded: list[tuple[str, str]] = [(property_name, property_value)]

    if property_name in CSS_PROPERTY_SHORTHANDS:
        longhand_properties = list(declaration.get("longhand_properties") or [])
        if not longhand_properties:
            try:
                payload = cdp.send(
                    "CSS.getLonghandProperties",
                    {
                        "shorthandName": property_name,
                        "value": property_value,
                    },
                )
            except Exception:
                payload = {}

            longhand_properties = (
                payload.get("longhandProperties")
                or payload.get("properties")
                or payload.get("cssProperties")
                or []
            )
        for property_payload in longhand_properties:
            longhand_name = property_payload.get("name")
            longhand_value = property_payload.get("value")
            longhand_spec = get_css_property(longhand_name)
            if not longhand_name or longhand_value in (None, "") or longhand_spec is None:
                continue
            if _is_implicit_longhand_value(str(longhand_value)):
                continue
            canonical_longhand_name = longhand_spec.value
            expanded.append(
                (
                    canonical_longhand_name,
                    _normalize_css_value(canonical_longhand_name, str(longhand_value)),
                )
            )

    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in expanded:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)

    cache[cache_key] = deduped
    return deduped


def _is_implicit_longhand_value(value: str) -> bool:
    return _strip_important_annotation(value).strip().lower() in {
        "initial",
        "inherit",
        "unset",
        "revert",
        "revert-layer",
    }


def _resolve_candidate_value(
    cdp: Any,
    *,
    frontend_node_id: int,
    property_name: str,
    candidate_value: str,
    source_computed_styles: dict[str, str],
    source_parent_computed_styles: dict[str, str],
    resolve_cache: dict[tuple[int, str, str], str | None],
) -> str | None:
    normalized_candidate = _normalize_css_value(property_name, candidate_value)
    lower_candidate = normalized_candidate.lower()

    if lower_candidate == "currentcolor":
        return source_computed_styles.get("color")

    if lower_candidate == "inherit":
        return source_parent_computed_styles.get(property_name)

    if lower_candidate in {"initial", "unset", "revert", "revert-layer"} or _should_attempt_resolve(
        candidate_value
    ):
        resolved = _resolve_css_value(
            cdp,
            frontend_node_id,
            property_name,
            candidate_value,
            resolve_cache,
        )
        if resolved not in (None, ""):
            return _normalize_css_value(property_name, resolved)

    return normalized_candidate


def _property_candidates(
    cdp: Any,
    *,
    target_property: str,
    target_computed_value: str,
    style_entries: list[dict[str, Any]],
    style_ids_by_key: dict[tuple[Any, ...], str],
    declaration_ids_by_signature: dict[tuple[str, str, str, bool, bool], str],
    expansion_cache: dict[tuple[str, str], list[tuple[str, str]]],
    resolve_cache: dict[tuple[int, str, str], str | None],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for entry in style_entries:
        inherited_from_element_id = entry.get("_inherited_from_element_id")
        if inherited_from_element_id and target_property not in _INHERITED_SCOPE_PROPERTIES:
            continue

        style_id = style_ids_by_key[entry["_inventory_key"]]
        for declaration in entry["declarations"]:
            for resolved_property, resolved_value in _expand_declaration_targets(
                cdp,
                declaration,
                expansion_cache,
            ):
                if resolved_property != target_property:
                    continue

                candidate_value = _resolve_candidate_value(
                    cdp,
                    frontend_node_id=entry["_resolution_frontend_node_id"],
                    property_name=resolved_property,
                    candidate_value=resolved_value,
                    source_computed_styles=entry["_source_computed_styles"],
                    source_parent_computed_styles=entry["_source_parent_computed_styles"],
                    resolve_cache=resolve_cache,
                )
                if candidate_value != target_computed_value:
                    continue

                candidates.append(
                    {
                        "style_id": style_id,
                        "kind": entry["kind"],
                        "origin": entry["origin"],
                        "declared_property": declaration["name"],
                        "declaration_id": declaration_ids_by_signature.get(
                            (
                                style_id,
                                declaration["name"],
                                declaration["value"],
                                declaration["important"],
                                declaration["implicit"],
                            )
                        ),
                        "important": declaration["important"],
                        "specificity": entry["specificity"],
                        "layer_order": entry["layer_order"],
                        "inherited_from_element_id": inherited_from_element_id,
                        "source_order": (
                            entry["_sort_key"],
                            declaration["declaration_order"],
                        ),
                    }
                )

    return candidates


def _resolve_element_computed_styles(
    cdp: Any,
    *,
    computed_styles: dict[str, str],
    style_entries: list[dict[str, Any]],
    style_ids_by_key: dict[tuple[Any, ...], str],
    declaration_ids_by_signature: dict[tuple[str, str, str, bool, bool], str],
    expansion_cache: dict[tuple[str, str], list[tuple[str, str]]],
    resolve_cache: dict[tuple[int, str, str], str | None],
) -> dict[str, ComputedStyleValueModel]:
    resolved_styles: dict[str, ComputedStyleValueModel] = {}
    candidate_property_names: set[str] = set()

    for entry in style_entries:
        for declaration in entry["declarations"]:
            for resolved_property, _ in _expand_declaration_targets(
                cdp,
                declaration,
                expansion_cache,
            ):
                candidate_property_names.add(resolved_property)

    for property_name in sorted(candidate_property_names):
        if property_name not in computed_styles:
            continue
        computed_value = computed_styles[property_name]
        candidates = _property_candidates(
            cdp,
            target_property=property_name,
            target_computed_value=computed_value,
            style_entries=style_entries,
            style_ids_by_key=style_ids_by_key,
            declaration_ids_by_signature=declaration_ids_by_signature,
            expansion_cache=expansion_cache,
            resolve_cache=resolve_cache,
        )

        direct_candidates = [
            candidate
            for candidate in candidates
            if not candidate.get("inherited_from_element_id")
        ]
        inherited_candidates = [
            candidate
            for candidate in candidates
            if candidate.get("inherited_from_element_id")
        ]
        candidate_pool = direct_candidates or inherited_candidates

        if not candidate_pool:
            resolved_styles[property_name] = ComputedStyleValueModel(
                computed_value=computed_value,
                resolution_status="unresolved",
            )
            continue

        ranked_candidates = sorted(candidate_pool, key=_cascade_sort_key)
        winner = ranked_candidates[-1]
        if len(ranked_candidates) > 1 and _cascade_sort_key(ranked_candidates[-1]) == _cascade_sort_key(
            ranked_candidates[-2]
        ):
            resolved_styles[property_name] = ComputedStyleValueModel(
                computed_value=computed_value,
                resolution_status="ambiguous_match",
            )
            continue

        resolved_styles[property_name] = ComputedStyleValueModel(
            computed_value=computed_value,
            style_id=winner["style_id"],
            declared_property=winner["declared_property"],
            declaration_id=winner.get("declaration_id"),
            kind=winner["kind"],
            inherited_from_element_id=winner.get("inherited_from_element_id"),
            resolution_status="exact_match",
        )

    return resolved_styles


def collect_style_information(
    cdp: Any,
    raw_nodes: list[dict[str, Any]],
    stylesheet_headers: dict[str, dict[str, Any]],
    *,
    include_user_agent_rules: bool,
) -> tuple[dict[int, dict[str, Any]], StyleInventoryModel, ColorInventoryModel]:
    if not raw_nodes:
        return {}, StyleInventoryModel(), ColorInventoryModel()

    backend_node_ids = [node["backend_node_id"] for node in raw_nodes]
    backend_to_node_id = {node["backend_node_id"]: node["node_id"] for node in raw_nodes}
    raw_nodes_by_backend = {node["backend_node_id"]: node for node in raw_nodes}
    raw_nodes_by_source = {node["source_index"]: node for node in raw_nodes}

    cdp.send("DOM.getDocument", {"depth": 0})
    frontend = cdp.send("DOM.pushNodesByBackendIdsToFrontend", {"backendNodeIds": backend_node_ids})
    frontend_node_ids = frontend.get("nodeIds", [])
    backend_to_frontend_node_id = {
        backend_node_id: frontend_node_id
        for backend_node_id, frontend_node_id in zip(backend_node_ids, frontend_node_ids)
        if frontend_node_id
    }

    computed_styles_by_backend = {
        node["backend_node_id"]: _computed_style_map(node)
        for node in raw_nodes
    }

    aggregate_styles: dict[tuple[Any, ...], dict[str, Any]] = {}
    palette_usage: dict[str, dict[str, Any]] = {}
    node_style_entries: dict[int, list[dict[str, Any]]] = defaultdict(list)
    node_backgrounds: dict[int, tuple[list[str] | None, str | None]] = {}
    declaration_seed = 0
    expansion_cache: dict[tuple[str, str], list[tuple[str, str]]] = {}
    resolve_cache: dict[tuple[int, str, str], str | None] = {}

    for backend_node_id in backend_node_ids:
        frontend_node_id = backend_to_frontend_node_id.get(backend_node_id)
        if not frontend_node_id:
            continue

        raw_node = raw_nodes_by_backend[backend_node_id]
        computed_styles = computed_styles_by_backend[backend_node_id]
        parent_source_index = raw_node.get("parent_source_index")
        parent_raw_node = raw_nodes_by_source.get(parent_source_index) if isinstance(parent_source_index, int) else None
        parent_computed_styles = (
            computed_styles_by_backend.get(parent_raw_node["backend_node_id"], {})
            if parent_raw_node
            else {}
        )

        try:
            matched = cdp.send("CSS.getMatchedStylesForNode", {"nodeId": frontend_node_id})
        except Exception:
            node_backgrounds[backend_node_id] = (None, None)
            continue

        layer_orders = _fetch_layer_orders(cdp, frontend_node_id)

        for inline_kind, style_obj in (
            ("inline", matched.get("inlineStyle") or {}),
            ("attributes", matched.get("attributesStyle") or {}),
        ):
            entry = _build_inline_entry(
                style_obj,
                stylesheet_headers,
                kind=inline_kind,
                inherited_from_element_id=None,
                resolution_frontend_node_id=frontend_node_id,
                source_computed_styles=computed_styles,
                source_parent_computed_styles=parent_computed_styles,
                declaration_seed=declaration_seed,
            )
            if not entry:
                continue
            declaration_seed += 1
            entry["_inventory_key"] = _register_style_inventory_entry(
                aggregate_styles,
                entry=entry,
                node_id=backend_to_node_id[backend_node_id],
            )
            node_style_entries[backend_node_id].append(entry)

        for rule_entry in matched.get("matchedCSSRules", []) or []:
            entry = _build_rule_entry(
                rule_entry,
                stylesheet_headers,
                layer_orders,
                inherited_from_element_id=None,
                resolution_frontend_node_id=frontend_node_id,
                source_computed_styles=computed_styles,
                source_parent_computed_styles=parent_computed_styles,
                declaration_seed=declaration_seed,
            )
            if not entry:
                continue
            if not include_user_agent_rules and entry["origin"] == "user-agent":
                continue
            declaration_seed += 1
            entry["_inventory_key"] = _register_style_inventory_entry(
                aggregate_styles,
                entry=entry,
                node_id=backend_to_node_id[backend_node_id],
            )
            node_style_entries[backend_node_id].append(entry)

        ancestor_chain: list[dict[str, Any]] = []
        current_parent = parent_raw_node
        while current_parent is not None:
            ancestor_chain.append(current_parent)
            next_parent_source = current_parent.get("parent_source_index")
            current_parent = (
                raw_nodes_by_source.get(next_parent_source)
                if isinstance(next_parent_source, int)
                else None
            )

        for inherited_index, inherited_entry in enumerate(matched.get("inherited", []) or []):
            ancestor_raw_node = ancestor_chain[inherited_index] if inherited_index < len(ancestor_chain) else None
            ancestor_frontend_node_id = (
                backend_to_frontend_node_id.get(ancestor_raw_node["backend_node_id"])
                if ancestor_raw_node
                else frontend_node_id
            )
            ancestor_computed_styles = (
                computed_styles_by_backend.get(ancestor_raw_node["backend_node_id"], {})
                if ancestor_raw_node
                else parent_computed_styles
            )
            ancestor_parent_computed_styles = {}
            if ancestor_raw_node:
                ancestor_parent_source = ancestor_raw_node.get("parent_source_index")
                ancestor_parent_node = (
                    raw_nodes_by_source.get(ancestor_parent_source)
                    if isinstance(ancestor_parent_source, int)
                    else None
                )
                if ancestor_parent_node:
                    ancestor_parent_computed_styles = computed_styles_by_backend.get(
                        ancestor_parent_node["backend_node_id"],
                        {},
                    )

            inherited_from_element_id = ancestor_raw_node["node_id"] if ancestor_raw_node else None

            entry = _build_inline_entry(
                inherited_entry.get("inlineStyle") or {},
                stylesheet_headers,
                kind="inline",
                inherited_from_element_id=inherited_from_element_id,
                resolution_frontend_node_id=ancestor_frontend_node_id,
                source_computed_styles=ancestor_computed_styles,
                source_parent_computed_styles=ancestor_parent_computed_styles,
                declaration_seed=declaration_seed,
            )
            if entry:
                declaration_seed += 1
                entry["_inventory_key"] = _register_style_inventory_entry(
                    aggregate_styles,
                    entry=entry,
                    node_id=backend_to_node_id[backend_node_id],
                )
                node_style_entries[backend_node_id].append(entry)

            for rule_entry in inherited_entry.get("matchedCSSRules", []) or []:
                entry = _build_rule_entry(
                    rule_entry,
                    stylesheet_headers,
                    layer_orders,
                    inherited_from_element_id=inherited_from_element_id,
                    resolution_frontend_node_id=ancestor_frontend_node_id,
                    source_computed_styles=ancestor_computed_styles,
                    source_parent_computed_styles=ancestor_parent_computed_styles,
                    declaration_seed=declaration_seed,
                )
                if not entry:
                    continue
                if not include_user_agent_rules and entry["origin"] == "user-agent":
                    continue
                declaration_seed += 1
                entry["_inventory_key"] = _register_style_inventory_entry(
                    aggregate_styles,
                    entry=entry,
                    node_id=backend_to_node_id[backend_node_id],
                )
                node_style_entries[backend_node_id].append(entry)

        try:
            background_payload = cdp.send("CSS.getBackgroundColors", {"nodeId": frontend_node_id})
        except Exception:
            background_payload = None
        node_backgrounds[backend_node_id] = _normalize_background_colors(background_payload)

        direct_property_names = {
            declaration["name"]
            for entry in node_style_entries[backend_node_id]
            if not entry.get("_inherited_from_element_id") and entry.get("origin") == "author"
            for declaration in entry["declarations"]
            if declaration["name"] in _COLOR_VALUE_PROPERTIES
        }
        _collect_palette_usage(
            palette_usage,
            raw_node,
            computed_styles,
            direct_property_names,
        )

    styles_inventory, style_ids_by_key = _build_styles_inventory(aggregate_styles)
    declaration_ids_by_signature = {
        (
            style.style_id,
            declaration.name,
            declaration.value,
            declaration.important,
            declaration.implicit,
        ): declaration.declaration_id
        for style in styles_inventory
        for declaration in style.declarations
        if declaration.declaration_id
    }
    color_inventory = ColorInventoryModel.build_from_usage_map(palette_usage)

    element_traces: dict[int, dict[str, Any]] = {}
    for backend_node_id in backend_node_ids:
        computed_styles = computed_styles_by_backend.get(backend_node_id, {})
        resolved_computed_styles = _resolve_element_computed_styles(
            cdp,
            computed_styles=computed_styles,
            style_entries=node_style_entries.get(backend_node_id, []),
            style_ids_by_key=style_ids_by_key,
            declaration_ids_by_signature=declaration_ids_by_signature,
            expansion_cache=expansion_cache,
            resolve_cache=resolve_cache,
        )
        background_colors, effective_background = node_backgrounds.get(backend_node_id, (None, None))
        element_traces[backend_node_id] = {
            "computed_styles": resolved_computed_styles,
            "background_colors": background_colors,
            "effective_background": effective_background,
        }

    return element_traces, styles_inventory, color_inventory
