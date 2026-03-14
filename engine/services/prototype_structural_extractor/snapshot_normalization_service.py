from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import re
from typing import Any

from engine.enums.scope.css_properties import (
    CSS_PROPERTIES_BY_ID,
    CSS_PROPERTY_COMPUTED_ALIASES,
)
from engine.models.prototype_structural_extractor.snapshot_models import (
    RenderSnapshot,
    SnapshotNode,
    SnapshotOptions,
)

_RGBA_ALPHA_RE = re.compile(r"^rgba\((.+)\)$", re.IGNORECASE)
_HSLA_ALPHA_RE = re.compile(r"^hsla\((.+)\)$", re.IGNORECASE)
_SPACE_ALPHA_COLOR_RE = re.compile(r"^(?:rgb|hsl)\((.+)/(.+)\)$", re.IGNORECASE)
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


def normalize_snapshot_nodes(
    raw_nodes: list[dict[str, Any]],
    style_traces: dict[int, dict[str, Any]],
    rules_used: list[dict[str, Any]],
    palette: list[dict[str, Any]],
    *,
    options: SnapshotOptions,
    base_path: str,
    document_metrics: dict[str, Any],
) -> RenderSnapshot:
    filtered_raw_nodes = [
        node
        for node in raw_nodes
        if options.include_invisible or node["flags"].get("is_visible")
    ]
    retained_source_indexes = {node["source_index"] for node in filtered_raw_nodes}

    snapshot_nodes: list[SnapshotNode] = []
    source_index_to_snapshot_id = {
        node["source_index"]: node["node_id"]
        for node in filtered_raw_nodes
    }
    children_map: dict[str, list[str]] = {node["node_id"]: [] for node in filtered_raw_nodes}
    retained_parent_map: dict[str, str | None] = {}

    for raw_node in filtered_raw_nodes:
        parent_source_index = raw_node.get("parent_source_index")
        while isinstance(parent_source_index, int) and parent_source_index not in retained_source_indexes:
            parent_source_index = next(
                (
                    candidate.get("parent_source_index")
                    for candidate in raw_nodes
                    if candidate["source_index"] == parent_source_index
                ),
                None,
            )

        parent_id = (
            source_index_to_snapshot_id[parent_source_index]
            if isinstance(parent_source_index, int) and parent_source_index in source_index_to_snapshot_id
            else None
        )
        retained_parent_map[raw_node["node_id"]] = parent_id
        if parent_id:
            children_map.setdefault(parent_id, []).append(raw_node["node_id"])

    for raw_node in filtered_raw_nodes:
        backend_node_id = raw_node["backend_node_id"]
        node_trace = style_traces.get(backend_node_id, {})
        computed_styles = _filter_computed_styles(
            raw_node["styles"].get("computed", []),
            node_trace,
        )

        raw_node["styles"] = {
            "computed": computed_styles or None,
            "background_colors": _normalize_background_values(node_trace.get("background_colors")),
            "effective_background": _normalize_color_value("background-color", node_trace.get("effective_background")),
        }
        raw_node["style_trace"] = {
            "tracked_styles": node_trace.get("tracked_styles"),
        }
        raw_node["parent_id"] = retained_parent_map.get(raw_node["node_id"])
        raw_node["children_ids"] = tuple(sorted(children_map.get(raw_node["node_id"], [])))
        raw_node["flags"]["is_leaf"] = len(raw_node["children_ids"]) == 0
        raw_node["flags"]["has_siblings"] = bool(
            raw_node["parent_id"] and len(children_map.get(raw_node["parent_id"], [])) > 1
        )

        normalized = _prune_empty(
            {
                "node_id": raw_node["node_id"],
                "backend_node_id": raw_node["backend_node_id"],
                "parent_id": raw_node["parent_id"],
                "document_order": raw_node["document_order"],
                "identity": raw_node["identity"],
                "layout": raw_node["layout"],
                "styles": raw_node["styles"],
                "text": raw_node["text"],
                "flags": raw_node["flags"],
                "children_ids": raw_node["children_ids"],
                "paint_order": raw_node.get("paint_order"),
                "style_trace": raw_node["style_trace"],
            }
        )
        snapshot_nodes.append(SnapshotNode(**normalized))

    metadata = {
        "module": "prototype_structural_extractor.prototype_state_pipeline",
        "basePath": base_path,
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "nodeCount": len(snapshot_nodes),
        "options": asdict(options),
    }

    return RenderSnapshot(
        metadata=_prune_empty(metadata),
        document=_prune_empty(document_metrics),
        nodes=tuple(snapshot_nodes),
        rules_used=tuple(_prune_empty(rule) for rule in rules_used),
        palette=tuple(_prune_empty(entry) for entry in palette),
    )


def _filter_computed_styles(computed_values: list[str], style_trace: dict[str, Any]) -> dict[str, Any]:
    declarations = set()
    for origin_entries in (style_trace.get("tracked_styles") or {}).values():
        for rule in origin_entries:
            for declaration in rule.get("declarations", []):
                name = declaration.get("name")
                if name:
                    declarations.add(name)

    filtered: dict[str, Any] = {}
    for raw_value in computed_values:
        if ":" not in raw_value:
            continue
        name, value = raw_value.split(":", 1)
        property_name = CSS_PROPERTY_COMPUTED_ALIASES.get(name, name)
        if property_name not in CSS_PROPERTIES_BY_ID:
            continue
        spec = CSS_PROPERTIES_BY_ID[property_name]
        shorthand_targets = {child.value for child in spec.shorthand_for}
        related_shorthands = {spec.longhand_of.value} if spec.longhand_of else set()
        if property_name in declarations or shorthand_targets.intersection(declarations) or related_shorthands.intersection(declarations):
            normalized_value = _normalize_color_value(property_name, value)
            if normalized_value in ("", None):
                continue
            filtered[property_name] = normalized_value
    return filtered


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, inner in value.items():
            keep_empty = key in {"children_ids", "node_ids", "styles", "style_trace", "usage"}
            if inner in (None, "", (), [], {}) and not keep_empty:
                continue
            normalized = _prune_empty(inner)
            if normalized in (None, "", (), [], {}) and not keep_empty:
                continue
            cleaned[key] = normalized
        return cleaned

    if isinstance(value, list):
        return [_prune_empty(item) for item in value if item not in (None, "", {}, ())]

    if isinstance(value, tuple):
        return tuple(_prune_empty(item) for item in value if item not in (None, "", {}, ()))

    return value


def _normalize_background_values(values: list[str] | None) -> list[str] | None:
    if not values:
        return None
    normalized_values = []
    for value in values:
        normalized = _normalize_color_value("background-color", value)
        if not normalized:
            continue
        if normalized not in normalized_values:
            normalized_values.append(normalized)
    return normalized_values or None


def _normalize_color_value(property_name: str, value: Any) -> str | None:
    if value in (None, ""):
        return None

    normalized = str(value).strip()
    if property_name not in _PURE_COLOR_PROPERTIES:
        return normalized

    lower = normalized.lower()
    if lower == "transparent" or _is_alpha_zero_color(lower):
        return "transparent"
    return normalized


def _is_alpha_zero_color(value: str) -> bool:
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
