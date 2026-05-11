from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from engine.adapters.color_service import color_registry
from engine.adapters.browser.render_models import RenderSnapshot, SnapshotOptions
from engine.domain.enums.scope.css_properties import CssPropertyCategory, get_css_property
from engine.domain.models.color import ColorCatalog
from engine.domain.models.element import Element, Property

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
_UNRESOLVED_EFFECT_PROPERTIES = {"background-image", "box-shadow", "filter", "text-shadow"}


def normalize_snapshot_nodes(
    raw_nodes: list[dict[str, Any]],
    style_traces: dict[int, dict[str, Any]],
    *,
    colors_inventory: ColorCatalog,
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

    snapshot_nodes: list[Element] = []
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
        computed_styles = _filter_computed_styles(node_trace.get("computed_styles", {}))
        effective_background = _normalize_color_value(
            "background-color",
            node_trace.get("effective_background"),
        )

        parent_id = retained_parent_map.get(raw_node["node_id"])
        children_ids = tuple(sorted(children_map.get(raw_node["node_id"], [])))
        flags = raw_node["flags"]
        flags["is_leaf"] = len(children_ids) == 0
        flags["has_siblings"] = bool(parent_id and len(children_map.get(parent_id, [])) > 1)

        properties = tuple(
            _build_property(property_name, payload, colors_inventory)
            for property_name, payload in sorted(computed_styles.items())
        )

        identity = dict(raw_node.get("identity") or {})
        layout = dict(raw_node.get("layout") or {})
        absolute_bounds = dict(layout.get("absolute_bounds") or {})
        snapshot_nodes.append(
            Element.build(
                {
                    "node_id": raw_node["node_id"],
                    "backend_node_id": backend_node_id,
                    "parent_id": parent_id,
                    "children_ids": children_ids,
                    "document_order": raw_node["document_order"],
                    "tag_name": identity.get("tag"),
                    "node_name": identity.get("node_name"),
                    "html_id": identity.get("id"),
                    "name": identity.get("name"),
                    "role": identity.get("role"),
                    "class_names": tuple(identity.get("class_list") or ()),
                    "data_attributes": dict(identity.get("data_attributes") or {}),
                    "attributes": dict(identity.get("attributes") or {}),
                    "selector": identity.get("selector_hint"),
                    "xpath": identity.get("xpath"),
                    "related_media": dict(identity.get("related_media") or {}),
                    "text": raw_node.get("text"),
                    "paint_order": raw_node.get("paint_order"),
                    "x": layout.get("x"),
                    "y": layout.get("y"),
                    "width": layout.get("width"),
                    "height": layout.get("height"),
                    "left": absolute_bounds.get("left"),
                    "top": absolute_bounds.get("top"),
                    "right": absolute_bounds.get("right"),
                    "bottom": absolute_bounds.get("bottom"),
                    "is_visible": flags.get("is_visible"),
                    "is_leaf": flags.get("is_leaf"),
                    "has_siblings": flags.get("has_siblings"),
                    "is_text_node": flags.get("is_text_node"),
                    "is_out_of_scope": flags.get("is_out_of_scope"),
                    "is_stacking_context": flags.get("is_stacking_context"),
                    "effective_background": effective_background,
                    "properties": [property_model.to_dict() for property_model in properties],
                }
            )
        )

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
    )


def _build_property(
    property_name: str,
    payload: Any,
    colors_inventory: ColorCatalog,
) -> Property:
    computed_style = payload if isinstance(payload, dict) else {}
    color_entry = colors_inventory.entry_by_value(str(computed_style.get("computed_value") or ""))
    return Property.from_computed_style(
        name=property_name,
        computed_style=computed_style,
        color_id=color_entry.color_id if color_entry is not None else None,
    )


def _filter_computed_styles(computed_styles: dict[str, Any]) -> dict[str, Any]:
    filtered: dict[str, Any] = {}
    for property_name, payload in (computed_styles or {}).items():
        property_spec = get_css_property(property_name)
        if property_spec is None:
            continue
        canonical_name = property_spec.value
        if isinstance(payload, dict):
            raw_payload = payload
        else:
            continue

        computed_value = _normalize_color_value(
            canonical_name,
            raw_payload.get("computed_value"),
        )
        if computed_value in ("", None):
            continue
        has_authored_link = any(
            raw_payload.get(key)
            for key in ("style_id", "declared_property", "declaration_id", "inherited_from_element_id")
        )
        if (
            not has_authored_link
            and (
                CssPropertyCategory.EFFECT not in property_spec.categories
                or canonical_name not in _UNRESOLVED_EFFECT_PROPERTIES
            )
        ):
            continue

        normalized_payload = {
            "computed_value": computed_value,
        }
        if raw_payload.get("style_id"):
            normalized_payload["style_id"] = raw_payload["style_id"]
        if raw_payload.get("declared_property"):
            normalized_payload["declared_property"] = raw_payload["declared_property"]
        if raw_payload.get("declaration_id"):
            normalized_payload["declaration_id"] = raw_payload["declaration_id"]
        if raw_payload.get("inherited_from_element_id"):
            normalized_payload["inherited_from_element_id"] = raw_payload[
                "inherited_from_element_id"
            ]

        filtered[canonical_name] = normalized_payload
    return filtered


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, inner in value.items():
            keep_empty = key in {"children_ids", "node_ids", "usage", "properties"}
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


def _normalize_color_value(property_name: str, value: Any) -> str | None:
    if value in (None, ""):
        return None

    normalized = str(value).strip()
    if property_name not in _PURE_COLOR_PROPERTIES:
        return normalized

    return color_registry.normalize_css_color_token(normalized)
