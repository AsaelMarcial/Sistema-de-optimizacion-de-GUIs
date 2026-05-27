from __future__ import annotations

from collections import defaultdict
import re
from typing import Any, Mapping

from engine.adapters.color_service import color_registry
from engine.domain.enums.scope.css_properties import (
    CSS_PROPERTIES,
    getColorSupportedProperties,
)
from engine.domain.models.element import resolve_element_computed_styles
from engine.domain.models.style import AtRuleContext, StyleCatalog
from engine.domain.enums.types.style import (
    RuleType,
    StyleSourceKind,
)

_IMPORTANT_SUFFIX_RE = re.compile(r"\s*!important\s*$", re.IGNORECASE)
_RESOLVE_VALUE_RE = re.compile(
    r"\b(?:var|calc|min|max|clamp|attr|color-mix)\(|currentColor\b",
    re.IGNORECASE,
)

_COMPOSITE_COLOR_PROPERTIES = frozenset(
    {
        "-webkit-text-stroke",
        "background",
        "border",
        "caret",
        "column-rule",
        "outline",
        "text-decoration",
        "text-emphasis",
    }
)
_EFFECT_COLOR_PROPERTIES = frozenset(
    {
        "background-image",
        "backdrop-filter",
        "border-image",
        "border-image-source",
        "box-shadow",
        "filter",
        "mask",
        "mask-border",
        "mask-border-source",
        "mask-image",
        "text-shadow",
    }
)
_PURE_COLOR_PROPERTIES = frozenset(
    property_name
    for property_name in getColorSupportedProperties()
    if property_name not in _COMPOSITE_COLOR_PROPERTIES
    and property_name not in _EFFECT_COLOR_PROPERTIES
)
_INHERITED_SCOPE_PROPERTIES = frozenset(
    {
        "accent-color",
        "caret-color",
        "color",
        "fill",
        "fill-opacity",
        "stroke",
        "stroke-opacity",
        "visibility",
    }
)
_SHORTHAND_PROPERTIES = frozenset(
    {
        "-webkit-text-stroke",
        "background",
        "border",
        "border-color",
        "caret",
        "column-rule",
        "outline",
        "text-decoration",
        "text-emphasis",
    }
)


def _normalize_property_name(value: str | None) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if normalized.startswith("--"):
        return normalized
    return normalized.lower()


def _coerce_property_name(value: str | None) -> str | None:
    property_name = _normalize_property_name(value)
    if not property_name:
        return None
    return property_name if property_name in CSS_PROPERTIES else None


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
        property_name = _coerce_property_name(name)
        if not name or value in (None, "") or property_name is None:
            continue

        canonical_name = property_name
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
                "longhand_properties": tuple(
                    longhand_name
                    for item in (prop.get("longhandProperties") or ())
                    if (longhand_name := _coerce_property_name(item)) is not None
                ),
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
        "start_line": start_line + 1,
        "start_column": start_column,
        "end_line": end_line + 1,
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


def _authored_source_kind(
    *,
    inline: bool = False,
    source_url: str | None = None,
) -> StyleSourceKind:
    if inline:
        return StyleSourceKind.INLINE
    if source_url:
        return StyleSourceKind.EXTERNAL
    return StyleSourceKind.EMBEDDED


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


def _extract_rule_selectors(rule_entry: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    selector_entries: list[dict[str, Any]] = []
    selector_payloads = (((rule_entry.get("rule") or {}).get("selectorList") or {}).get("selectors") or ())
    for index, payload in enumerate(selector_payloads):
        if not isinstance(payload, dict):
            continue
        text = str(payload.get("text") or "").strip()
        if not text:
            continue
        selector_entries.append(
            {
                "text": text,
                "order_in_group": index,
                "specificity": _specificity_tuple(payload.get("specificity")),
                "source_range": _normalize_source_range(payload.get("range")),
            }
        )
    if selector_entries:
        return tuple(selector_entries)

    selector_text = str((((rule_entry.get("rule") or {}).get("selectorList") or {}).get("text")) or "").strip()
    if not selector_text:
        return ()
    return tuple(
        {
            "text": item.strip(),
            "order_in_group": index,
            "specificity": None,
            "source_range": None,
        }
        for index, item in enumerate(selector_text.split(","))
        if item.strip()
    )


def _entry_at_context(
    *,
    layer_name: str | None,
) -> tuple[dict[str, Any], ...]:
    contexts: list[dict[str, Any]] = []
    if layer_name:
        contexts.append(
            {
                "rule_type": RuleType.LAYER,
                "text": layer_name,
                "source_range": None,
            }
        )
    return tuple(contexts)


def _build_inline_entry(
    style_obj: dict[str, Any],
    stylesheet_headers: dict[str, dict[str, Any]],
    *,
    owner_element_id: str,
    inherited_from_element_id: str | None,
    resolution_frontend_node_id: int,
    source_computed_styles: Mapping[str, str],
    source_parent_computed_styles: Mapping[str, str],
    declaration_seed: int,
) -> dict[str, Any] | None:
    declarations = _extract_declarations(style_obj)
    if not declarations:
        return None

    style_sheet_id = style_obj.get("styleSheetId")
    stylesheet_header = stylesheet_headers.get(style_sheet_id)
    source_range = _normalize_source_range(style_obj.get("range"))
    source_url = (stylesheet_header or {}).get("source_url")

    return {
        "source_kind": _authored_source_kind(inline=True, source_url=source_url),
        "origin": "author",
        "style_sheet_id": style_sheet_id,
        "selectors": (),
        "declarations": declarations,
        "matching_selector_index": None,
        "specificity": None,
        "source_range": source_range,
        "at_context": (),
        "layer_name": None,
        "layer_order": None,
        "source_url": source_url,
        "owner_element_id": owner_element_id,
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
    source_computed_styles: Mapping[str, str],
    source_parent_computed_styles: Mapping[str, str],
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
    selectors = _extract_rule_selectors(rule_entry)
    layer_name, layer_order = _extract_layer_metadata(rule, layer_orders)
    origin = _normalize_cascade_origin(rule.get("origin"))
    source_url = (stylesheet_header or {}).get("source_url")

    return {
        "source_kind": (
            "user-agent"
            if origin == "user-agent"
            else _authored_source_kind(source_url=source_url)
        ),
        "origin": origin,
        "style_sheet_id": style_sheet_id,
        "selectors": selectors,
        "declarations": declarations,
        "matching_selector_index": matching_selector_index,
        "specificity": specificity,
        "source_range": source_range,
        "at_context": _entry_at_context(layer_name=layer_name),
        "layer_name": layer_name,
        "layer_order": layer_order,
        "source_url": source_url,
        "owner_element_id": None,
        "_sort_key": _style_sort_key(stylesheet_header, source_range, declaration_seed),
        "_resolution_frontend_node_id": resolution_frontend_node_id,
        "_source_computed_styles": source_computed_styles,
        "_source_parent_computed_styles": source_parent_computed_styles,
        "_inherited_from_element_id": inherited_from_element_id,
    }


def _inventory_key(entry: dict[str, Any]) -> tuple[Any, ...]:
    return (
        entry["source_kind"],
        entry["style_sheet_id"],
        tuple(
            (
                selector["text"],
                selector.get("specificity"),
            )
            for selector in entry.get("selectors", ())
        ),
        tuple(sorted((entry["source_range"] or {}).items())),
        tuple(
            (
                context["rule_type"].value if hasattr(context["rule_type"], "value") else str(context["rule_type"]),
                context["text"],
            )
            for context in entry.get("at_context", ())
        ),
        entry["source_url"],
        entry["owner_element_id"],
        tuple(
            (
                declaration["name"],
                declaration["value"],
                declaration["important"],
                declaration["implicit"],
                declaration["declaration_order"],
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
            "source_kind": entry["source_kind"],
            "origin": entry["origin"],
            "style_sheet_id": entry["style_sheet_id"],
            "selectors": tuple(dict(selector) for selector in entry.get("selectors", ())),
            "declarations": tuple(dict(declaration) for declaration in entry["declarations"]),
            "source_range": entry["source_range"],
            "at_context": tuple(dict(context) for context in entry.get("at_context", ())),
            "layer_name": entry["layer_name"],
            "layer_order": entry["layer_order"],
            "source_url": entry["source_url"],
            "owner_element_id": entry["owner_element_id"],
            "node_ids": set(),
            "usage_count": 0,
            "_sort_key": entry["_sort_key"],
        }

    aggregate[key]["node_ids"].add(node_id)
    aggregate[key]["usage_count"] += 1
    return key


def _build_styles_inventory(
    aggregate: dict[tuple[Any, ...], dict[str, Any]],
) -> tuple[
    StyleCatalog,
    dict[tuple[Any, ...], str],
    dict[tuple[str, str, str, bool, bool], str],
    dict[tuple[tuple[Any, ...], int], str],
]:
    style_catalog = StyleCatalog()
    style_ids_by_key: dict[tuple[Any, ...], str] = {}
    declaration_ids_by_signature: dict[tuple[str, str, str, bool, bool], str] = {}
    selector_ids_by_key_and_index: dict[tuple[tuple[Any, ...], int], str] = {}

    for source_order, (inventory_key, entry) in enumerate(
        sorted(aggregate.items(), key=lambda item: item[1]["_sort_key"])
    ):
        source = style_catalog.add_source(
            kind=entry["source_kind"],
            source_order=source_order,
            stylesheet_id=entry.get("style_sheet_id"),
            href=entry.get("source_url"),
            owner_node_id=entry.get("owner_element_id"),
        )
        rule = source.add_rule(
            rule_type=RuleType.STYLE,
            at_rule_contexts=tuple(
                AtRuleContext(
                    name=(
                        context["rule_type"].value
                        if hasattr(context["rule_type"], "value")
                        else str(context["rule_type"])
                    ),
                    prelude=context["text"],
                )
                for context in entry.get("at_context", ())
            ),
            source_range=entry.get("source_range"),
            source_order=source_order,
        )
        for selector_payload in entry.get("selectors", ()):
            selector = rule.add_selector(
                text=selector_payload["text"],
                order_in_group=int(selector_payload.get("order_in_group") or 0),
                specificity=selector_payload.get("specificity"),
            )
            selector_ids_by_key_and_index[(inventory_key, selector.order_in_group)] = selector.selector_id
        for declaration_payload in entry["declarations"]:
            declaration = rule.add_declaration(
                name=declaration_payload["name"],
                value_text=declaration_payload["value"],
                important=bool(declaration_payload.get("important")),
                declaration_order=int(declaration_payload.get("declaration_order") or 0),
                source_range=declaration_payload.get("source_range"),
                covered_longhands=tuple(
                    str(item)
                    for item in declaration_payload.get("longhand_properties", ())
                ),
            )
            declaration_ids_by_signature[
                (
                    rule.rule_id,
                    declaration_payload["name"],
                    declaration_payload["value"],
                    bool(declaration_payload.get("important")),
                    bool(declaration_payload.get("implicit")),
                )
            ] = declaration.declaration_id
        style_ids_by_key[inventory_key] = rule.rule_id

    return (
        style_catalog,
        style_ids_by_key,
        declaration_ids_by_signature,
        selector_ids_by_key_and_index,
    )


def _computed_style_map(raw_node: dict[str, Any]) -> dict[str, str]:
    computed: dict[str, str] = {}
    for raw_value in raw_node.get("styles", {}).get("computed", []):
        if ":" not in raw_value:
            continue
        name, value = raw_value.split(":", 1)
        property_name = _coerce_property_name(name)
        if property_name is None:
            continue
        computed[property_name] = _normalize_css_value(property_name, value)
    return computed


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
    property_name = _coerce_property_name(property_name)
    if property_name is None:
        return None
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
    property_name = str(declaration["name"])
    property_value = declaration["value"]
    cache_key = (property_name, property_value)
    if cache_key in cache:
        return cache[cache_key]

    expanded: list[tuple[str, str]] = [(property_name, property_value)]

    if property_name in _SHORTHAND_PROPERTIES:
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
            if isinstance(property_payload, str):
                longhand_name = _coerce_property_name(property_payload)
                longhand_value = None
            else:
                longhand_name = _coerce_property_name(property_payload.get("name"))
                longhand_value = property_payload.get("value")
            if not longhand_name or longhand_value in (None, ""):
                continue
            if _is_implicit_longhand_value(str(longhand_value)):
                continue
            expanded.append(
                (
                    longhand_name,
                    _normalize_css_value(longhand_name, str(longhand_value)),
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
    source_computed_styles: Mapping[str, str],
    source_parent_computed_styles: Mapping[str, str],
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
    selector_ids_by_key_and_index: Mapping[tuple[tuple[Any, ...], int], str],
    expansion_cache: dict[tuple[str, str], list[tuple[str, str]]],
    resolve_cache: dict[tuple[int, str, str], str | None],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for entry in style_entries:
        inherited_from_element_id = entry.get("_inherited_from_element_id")
        if inherited_from_element_id and target_property not in _INHERITED_SCOPE_PROPERTIES:
            continue

        inventory_key = entry.get("_inventory_key")
        style_id = style_ids_by_key.get(inventory_key) if inventory_key is not None else None
        selector_id = None
        matching_selector_index = entry.get("matching_selector_index")
        if style_id and inventory_key is not None:
            if isinstance(matching_selector_index, int):
                selector_id = selector_ids_by_key_and_index.get((inventory_key, matching_selector_index))
            if selector_id is None and len(entry.get("selectors", ())) == 1:
                selector_id = selector_ids_by_key_and_index.get((inventory_key, 0))
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
                        "source_kind": entry["source_kind"],
                        "origin": entry["origin"],
                        "declared_property": declaration["name"],
                        "declaration_id": (
                            declaration_ids_by_signature.get(
                                (
                                    style_id,
                                    declaration["name"],
                                    declaration["value"],
                                    declaration["important"],
                                    declaration["implicit"],
                                )
                            )
                            if style_id
                            else None
                        ),
                        "important": declaration["important"],
                        "specificity": entry["specificity"],
                        "layer_order": entry["layer_order"],
                        "inherited_from_element_id": inherited_from_element_id,
                        "source_order": (
                            entry["_sort_key"],
                            declaration["declaration_order"],
                        ),
                        "selector_id": selector_id,
                    }
                )

    return candidates


def _candidate_map_for_element(
    cdp: Any,
    *,
    computed_styles: Mapping[str, str],
    style_entries: list[dict[str, Any]],
    style_ids_by_key: dict[tuple[Any, ...], str],
    declaration_ids_by_signature: dict[tuple[str, str, str, bool, bool], str],
    selector_ids_by_key_and_index: Mapping[tuple[tuple[Any, ...], int], str],
    expansion_cache: dict[tuple[str, str], list[tuple[str, str]]],
    resolve_cache: dict[tuple[int, str, str], str | None],
) -> dict[str, list[dict[str, Any]]]:
    candidates_by_property: dict[str, list[dict[str, Any]]] = {}
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
        candidates_by_property[property_name] = _property_candidates(
            cdp,
            target_property=property_name,
            target_computed_value=computed_value,
            style_entries=style_entries,
            style_ids_by_key=style_ids_by_key,
            declaration_ids_by_signature=declaration_ids_by_signature,
            selector_ids_by_key_and_index=selector_ids_by_key_and_index,
            expansion_cache=expansion_cache,
            resolve_cache=resolve_cache,
        )
    return candidates_by_property


def collect_style_information(
    cdp: Any,
    raw_nodes: list[dict[str, Any]],
    stylesheet_headers: dict[str, dict[str, Any]],
    *,
    include_user_agent_rules: bool,
) -> tuple[dict[int, dict[str, Any]], StyleCatalog]:
    if not raw_nodes:
        return {}, StyleCatalog()

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

        for _is_attribute_style, style_obj in (
            (False, matched.get("inlineStyle") or {}),
            (True, matched.get("attributesStyle") or {}),
        ):
            entry = _build_inline_entry(
                style_obj,
                stylesheet_headers,
                owner_element_id=backend_to_node_id[backend_node_id],
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
            if entry["origin"] == "user-agent":
                if include_user_agent_rules:
                    node_style_entries[backend_node_id].append(entry)
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
                owner_element_id=inherited_from_element_id or backend_to_node_id[backend_node_id],
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
                if entry["origin"] == "user-agent":
                    if include_user_agent_rules:
                        node_style_entries[backend_node_id].append(entry)
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

    (
        styles_inventory,
        style_ids_by_key,
        declaration_ids_by_signature,
        selector_ids_by_key_and_index,
    ) = _build_styles_inventory(aggregate_styles)

    def _mark_selector_used(style_id: str, selector_id: str | None) -> None:
        if not style_id:
            return
        try:
            style_rule = styles_inventory.get_rule(style_id)
        except Exception:
            return
        if selector_id:
            selector = style_rule.get_selector(selector_id)
            if selector is not None:
                selector.mark_used()
                return
        if len(style_rule.selectors) == 1:
            style_rule.selectors[0].mark_used()

    element_traces: dict[int, dict[str, Any]] = {}
    for backend_node_id in backend_node_ids:
        computed_styles = computed_styles_by_backend.get(backend_node_id, {})
        candidates_by_property = _candidate_map_for_element(
            cdp,
            computed_styles=computed_styles,
            style_entries=node_style_entries.get(backend_node_id, []),
            style_ids_by_key=style_ids_by_key,
            declaration_ids_by_signature=declaration_ids_by_signature,
            selector_ids_by_key_and_index=selector_ids_by_key_and_index,
            expansion_cache=expansion_cache,
            resolve_cache=resolve_cache,
        )
        resolved_computed_styles = resolve_element_computed_styles(
            computed_styles=computed_styles,
            candidates_by_property=candidates_by_property,
            mark_selector_used=_mark_selector_used,
        )
        background_colors, effective_background = node_backgrounds.get(backend_node_id, (None, None))
        element_traces[backend_node_id] = {
            "computed_styles": resolved_computed_styles,
            "background_colors": background_colors,
            "effective_background": effective_background,
        }

    return element_traces, styles_inventory
