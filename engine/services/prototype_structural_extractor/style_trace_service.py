from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from engine.enums.scope.css_properties import CSS_PROPERTIES_BY_ID, CSS_PROPERTY_SHORTHANDS

_RGBA_ALPHA_RE = re.compile(r"^rgba\((.+)\)$", re.IGNORECASE)
_HSLA_ALPHA_RE = re.compile(r"^hsla\((.+)\)$", re.IGNORECASE)
_SPACE_ALPHA_COLOR_RE = re.compile(r"^(?:rgb|hsl)\((.+)/(.+)\)$", re.IGNORECASE)
_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_FUNCTION_COLOR_RE = re.compile(r"(?:rgba?|hsla?)\([^)]+\)", re.IGNORECASE)
_MULTISPACE_RE = re.compile(r"\s+")

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
    "box-shadow",
    "caret",
    "column-rule",
    "outline",
    "text-decoration",
    "text-emphasis",
    "text-shadow",
}


def register_stylesheet_headers(cdp: Any) -> dict[str, dict[str, Any]]:
    headers: dict[str, dict[str, Any]] = {}

    def _on_style_added(params: dict[str, Any]) -> None:
        header = (params or {}).get("header", {})
        style_sheet_id = header.get("styleSheetId")
        if not style_sheet_id:
            return
        headers[style_sheet_id] = {
            "style_sheet_id": style_sheet_id,
            "origin": header.get("origin"),
            "source_url": header.get("sourceURL") or None,
            "title": header.get("title") or None,
            "is_inline": bool(header.get("isInline", False)),
        }

    cdp.on("CSS.styleSheetAdded", _on_style_added)
    return headers


def _normalize_css_value(property_name: str, value: str) -> str:
    if property_name in _PURE_COLOR_PROPERTIES:
        return _normalize_color_token(value)
    return value.strip()


def _normalize_color_token(value: str) -> str:
    normalized = _MULTISPACE_RE.sub(" ", str(value).strip()).strip()
    if not normalized:
        return normalized

    lower = normalized.lower()
    if lower == "transparent":
        return "transparent"

    if _is_alpha_zero_color(lower):
        return "transparent"

    return lower if lower.startswith("#") else normalized


def _is_alpha_zero_color(value: str) -> bool:
    if value == "transparent":
        return True

    hex_value = value.lstrip("#")
    if len(hex_value) in {4, 8}:
        alpha = hex_value[-1] if len(hex_value) == 4 else hex_value[-2:]
        return alpha in {"0", "00"}

    rgba_match = _RGBA_ALPHA_RE.match(value)
    if rgba_match:
        parts = [part.strip() for part in rgba_match.group(1).split(",")]
        return len(parts) >= 4 and _alpha_is_zero(parts[3])

    hsla_match = _HSLA_ALPHA_RE.match(value)
    if hsla_match:
        parts = [part.strip() for part in hsla_match.group(1).split(",")]
        return len(parts) >= 4 and _alpha_is_zero(parts[3])

    slash_match = _SPACE_ALPHA_COLOR_RE.match(value)
    if slash_match:
        return _alpha_is_zero(slash_match.group(2))

    return False


def _alpha_is_zero(raw_alpha: str) -> bool:
    alpha = raw_alpha.strip().rstrip(")")
    if alpha.endswith("%"):
        try:
            return float(alpha[:-1].strip()) == 0
        except ValueError:
            return False

    try:
        return float(alpha) == 0
    except ValueError:
        return False


def _extract_declarations(style_obj: dict[str, Any]) -> list[dict[str, Any]]:
    declarations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, bool, bool]] = set()

    for prop in style_obj.get("cssProperties", []) or []:
        name = prop.get("name")
        value = prop.get("value")
        if not name or value in (None, "") or name not in CSS_PROPERTIES_BY_ID:
            continue

        normalized_value = _normalize_css_value(name, str(value))
        signature = (
            name,
            normalized_value,
            bool(prop.get("important", False)),
            bool(prop.get("implicit", False)),
        )
        if signature in seen:
            continue

        seen.add(signature)
        declarations.append(
            {
                "name": name,
                "value": normalized_value,
                "important": signature[2],
                "implicit": signature[3],
            }
        )

    return declarations


def _rule_kind(origin: str | None, stylesheet_header: dict[str, Any] | None, *, inherited: bool = False) -> str:
    if inherited:
        return "inherited"
    if origin == "user-agent":
        return "user-agent"
    if stylesheet_header and stylesheet_header.get("is_inline"):
        return "embedded"
    return "external"


def _summarize_rule_entry(
    rule_entry: dict[str, Any],
    stylesheet_headers: dict[str, dict[str, Any]],
    *,
    inherited: bool = False,
) -> dict[str, Any] | None:
    matching_selectors = rule_entry.get("matchingSelectors", []) or []
    if not matching_selectors:
        return None

    rule = rule_entry.get("rule", {})
    style = rule.get("style", {})
    declarations = _extract_declarations(style)
    if not declarations:
        return None

    style_sheet_id = style.get("styleSheetId")
    stylesheet_header = stylesheet_headers.get(style_sheet_id)
    selector_list = rule.get("selectorList", {})

    return {
        "kind": _rule_kind(rule.get("origin"), stylesheet_header, inherited=inherited),
        "origin": rule.get("origin"),
        "style_sheet_id": style_sheet_id,
        "selector_text": selector_list.get("text"),
        "declarations": declarations,
    }


def _build_inline_trace(style_obj: dict[str, Any], *, kind: str) -> dict[str, Any] | None:
    declarations = _extract_declarations(style_obj)
    if not declarations:
        return None

    return {
        "kind": kind,
        "origin": "author",
        "style_sheet_id": style_obj.get("styleSheetId"),
        "selector_text": None,
        "declarations": declarations,
    }


def _rule_key(
    *,
    kind: str,
    origin: str | None,
    style_sheet_id: str | None,
    selector_text: str | None,
    declarations: list[dict[str, Any]],
) -> tuple[Any, ...]:
    return (
        kind,
        origin,
        style_sheet_id,
        selector_text,
        tuple(
            (item["name"], str(item["value"]), item["important"], item["implicit"])
            for item in declarations
        ),
    )


def _aggregate_rule(
    aggregate: dict[tuple[Any, ...], dict[str, Any]],
    *,
    node_id: str,
    kind: str,
    origin: str | None,
    style_sheet_id: str | None,
    selector_text: str | None,
    declarations: list[dict[str, Any]],
) -> tuple[Any, ...]:
    key = _rule_key(
        kind=kind,
        origin=origin,
        style_sheet_id=style_sheet_id,
        selector_text=selector_text,
        declarations=declarations,
    )
    if key not in aggregate:
        aggregate[key] = {
            "kind": kind,
            "origin": origin,
            "style_sheet_id": style_sheet_id,
            "selector_text": selector_text,
            "declarations": declarations,
            "node_ids": set(),
            "usage_count": 0,
        }

    aggregate[key]["node_ids"].add(node_id)
    aggregate[key]["usage_count"] += 1
    return key


def _computed_style_map(raw_node: dict[str, Any]) -> dict[str, str]:
    computed: dict[str, str] = {}
    for raw_value in raw_node.get("styles", {}).get("computed", []):
        if ":" not in raw_value:
            continue
        name, value = raw_value.split(":", 1)
        computed[name] = _normalize_css_value(name, value)
    return computed


def _filter_inherited_rules(
    inherited_rules: list[dict[str, Any]],
    computed_styles: dict[str, str],
    direct_property_names: set[str],
) -> list[dict[str, Any]]:
    filtered_rules: list[dict[str, Any]] = []
    for rule in inherited_rules:
        filtered_declarations = [
            declaration
            for declaration in rule["declarations"]
            if _inherited_declaration_applies(declaration, computed_styles, direct_property_names)
        ]
        if filtered_declarations:
            filtered_rules.append({**rule, "declarations": filtered_declarations})
    return filtered_rules


def _inherited_declaration_applies(
    declaration: dict[str, Any],
    computed_styles: dict[str, str],
    direct_property_names: set[str],
) -> bool:
    property_name = declaration.get("name")
    if not property_name or property_name in direct_property_names:
        return False

    declared_value = _normalize_css_value(property_name, str(declaration.get("value", "")))
    if property_name in computed_styles:
        return computed_styles[property_name] == declared_value

    for longhand in CSS_PROPERTY_SHORTHANDS.get(property_name, ()):
        if longhand in computed_styles and computed_styles[longhand] == declared_value:
            return True

    return False


def _group_node_styles(
    grouped_entries: dict[str, list[dict[str, Any]]],
    style_ids_by_key: dict[tuple[Any, ...], str],
) -> dict[str, list[dict[str, Any]]]:
    tracked_styles: dict[str, list[dict[str, Any]]] = {}
    for origin, entries in grouped_entries.items():
        normalized_entries = []
        for entry in entries:
            style_id = style_ids_by_key.get(entry["rule_key"])
            if not style_id:
                continue
            normalized_entries.append(
                {
                    "style_id": style_id,
                    "declarations": entry["declarations"],
                }
            )
        if normalized_entries:
            tracked_styles[origin] = normalized_entries
    return tracked_styles


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


def _resolve_palette_targets(property_name: str, computed_styles: dict[str, str]) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    if property_name in computed_styles:
        targets.append((property_name, computed_styles[property_name]))

    for longhand in CSS_PROPERTY_SHORTHANDS.get(property_name, ()):
        if longhand in computed_styles:
            targets.append((longhand, computed_styles[longhand]))

    return targets


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

    if not colors and value.strip().lower() == "transparent":
        return []

    return colors


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


def collect_style_information(
    cdp: Any,
    raw_nodes: list[dict[str, Any]],
    stylesheet_headers: dict[str, dict[str, Any]],
    *,
    include_user_agent_rules: bool,
) -> tuple[dict[int, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not raw_nodes:
        return {}, [], []

    backend_node_ids = [node["backend_node_id"] for node in raw_nodes]
    backend_to_node_id = {node["backend_node_id"]: node["node_id"] for node in raw_nodes}
    raw_nodes_by_backend = {node["backend_node_id"]: node for node in raw_nodes}

    cdp.send("DOM.getDocument", {"depth": 0})
    frontend = cdp.send("DOM.pushNodesByBackendIdsToFrontend", {"backendNodeIds": backend_node_ids})
    node_ids = frontend.get("nodeIds", [])

    aggregate_rules: dict[tuple[Any, ...], dict[str, Any]] = {}
    palette_usage: dict[str, dict[str, Any]] = {}
    node_style_groups: dict[int, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    node_backgrounds: dict[int, tuple[list[str] | None, str | None]] = {}

    for backend_node_id, node_id in zip(backend_node_ids, node_ids):
        if not node_id:
            continue

        raw_node = raw_nodes_by_backend[backend_node_id]
        computed_styles = _computed_style_map(raw_node)

        try:
            matched = cdp.send("CSS.getMatchedStylesForNode", {"nodeId": node_id})
        except Exception as exc:
            node_style_groups[backend_node_id]["error"] = [{"style_id": "error", "declarations": [{"name": "error", "value": str(exc), "important": False, "implicit": False}]}]
            continue

        inline_style = _build_inline_trace(matched.get("inlineStyle") or {}, kind="inline")
        attribute_style = _build_inline_trace(matched.get("attributesStyle") or {}, kind="inline")

        matched_rules = [
            summary
            for entry in matched.get("matchedCSSRules", []) or []
            for summary in [_summarize_rule_entry(entry, stylesheet_headers)]
            if summary and (include_user_agent_rules or summary["kind"] != "user-agent")
        ]

        inherited_rules = [
            summary
            for inherited_entry in matched.get("inherited", []) or []
            for entry in inherited_entry.get("matchedCSSRules", []) or []
            for summary in [_summarize_rule_entry(entry, stylesheet_headers, inherited=True)]
            if summary and (include_user_agent_rules or summary["origin"] != "user-agent")
        ]

        direct_property_names = {
            declaration["name"]
            for trace in (inline_style, attribute_style)
            if trace
            for declaration in trace["declarations"]
        }
        direct_property_names.update(
            declaration["name"]
            for rule in matched_rules
            for declaration in rule["declarations"]
        )

        filtered_inherited_rules = _filter_inherited_rules(
            inherited_rules,
            computed_styles,
            direct_property_names,
        )

        try:
            background_payload = cdp.send("CSS.getBackgroundColors", {"nodeId": node_id})
        except Exception:
            background_payload = None
        node_backgrounds[backend_node_id] = _normalize_background_colors(background_payload)

        node_entries = node_style_groups[backend_node_id]

        for inline_trace in (inline_style, attribute_style):
            if not inline_trace:
                continue
            rule_key = _aggregate_rule(
                aggregate_rules,
                node_id=backend_to_node_id[backend_node_id],
                kind=inline_trace["kind"],
                origin=inline_trace["origin"],
                style_sheet_id=inline_trace.get("style_sheet_id"),
                selector_text=inline_trace.get("selector_text"),
                declarations=inline_trace["declarations"],
            )
            node_entries[inline_trace["kind"]].append(
                {
                    "rule_key": rule_key,
                    "declarations": inline_trace["declarations"],
                }
            )

        for rule in matched_rules + filtered_inherited_rules:
            rule_key = _aggregate_rule(
                aggregate_rules,
                node_id=backend_to_node_id[backend_node_id],
                kind=rule["kind"],
                origin=rule["origin"],
                style_sheet_id=rule.get("style_sheet_id"),
                selector_text=rule.get("selector_text"),
                declarations=rule["declarations"],
            )
            node_entries[rule["kind"]].append(
                {
                    "rule_key": rule_key,
                    "declarations": rule["declarations"],
                }
            )

        _collect_palette_usage(
            palette_usage,
            raw_node,
            computed_styles,
            direct_property_names,
        )

    sorted_rule_keys = sorted(
        aggregate_rules,
        key=lambda item: (
            aggregate_rules[item].get("style_sheet_id") or "",
            aggregate_rules[item].get("selector_text") or "",
            aggregate_rules[item].get("kind") or "",
        ),
    )
    style_ids_by_key = {key: f"style-{index}" for index, key in enumerate(sorted_rule_keys, start=1)}

    normalized_rules_used: list[dict[str, Any]] = []
    for key in sorted_rule_keys:
        aggregate_entry = aggregate_rules[key]
        normalized_rules_used.append(
            {
                "style_id": style_ids_by_key[key],
                "kind": aggregate_entry["kind"],
                "origin": aggregate_entry["origin"],
                "style_sheet_id": aggregate_entry["style_sheet_id"],
                "selector_text": aggregate_entry["selector_text"],
                "declarations": aggregate_entry["declarations"],
                "node_ids": sorted(aggregate_entry["node_ids"]),
                "usage_count": aggregate_entry["usage_count"],
            }
        )

    node_traces: dict[int, dict[str, Any]] = {}
    for backend_node_id in backend_node_ids:
        background_colors, effective_background = node_backgrounds.get(backend_node_id, (None, None))
        tracked_styles = _group_node_styles(node_style_groups.get(backend_node_id, {}), style_ids_by_key)
        node_traces[backend_node_id] = {
            "tracked_styles": tracked_styles or None,
            "background_colors": background_colors,
            "effective_background": effective_background,
        }

    return node_traces, normalized_rules_used, _normalize_palette(palette_usage)
