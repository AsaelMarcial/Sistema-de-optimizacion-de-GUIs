from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from engine.enums.scope import HTML_ELEMENTS_BY_ID
from engine.enums.scope.html_elements import IGNORED_HTML_TAGS, MEDIA_METADATA_ONLY_TAGS

_WHITESPACE_RE = re.compile(r"\s+")


def _decode_string(strings: list[str], index: int | None, default: str = "") -> str:
    if index is None or not isinstance(index, int) or index < 0 or index >= len(strings):
        return default
    return strings[index]


def _decode_sparse_value(strings: list[str], payload: dict[str, Any] | None, index: int) -> str:
    if not payload:
        return ""

    indexes = payload.get("index", [])
    values = payload.get("value", [])
    try:
        position = indexes.index(index)
    except ValueError:
        return ""

    value_index = values[position]
    if isinstance(value_index, int):
        return _decode_string(strings, value_index, "")
    if isinstance(value_index, str):
        return value_index
    return ""


def _decode_attributes(strings: list[str], raw_attributes: list[int]) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for idx in range(0, len(raw_attributes), 2):
        key = _decode_string(strings, raw_attributes[idx], "")
        value = _decode_string(strings, raw_attributes[idx + 1], "")
        if key:
            attributes[key] = value
    return attributes


def _build_children_map(parent_indexes: list[int]) -> dict[int, list[int]]:
    children_map: dict[int, list[int]] = {}
    for index, parent_index in enumerate(parent_indexes):
        if not isinstance(parent_index, int) or parent_index < 0:
            continue
        children_map.setdefault(parent_index, []).append(index)
    return children_map


def _build_layout_map(document: dict[str, Any]) -> dict[int, dict[str, Any]]:
    layout = document.get("layout") or {}
    node_indexes = layout.get("nodeIndex") or []
    bounds = layout.get("bounds") or []
    styles = layout.get("styles") or []
    paint_orders = layout.get("paintOrders") or []
    stacking_contexts = set((layout.get("stackingContexts") or {}).get("index", []))

    layout_map: dict[int, dict[str, Any]] = {}
    for offset, node_index in enumerate(node_indexes):
        layout_map[node_index] = {
            "bounds": bounds[offset] if offset < len(bounds) else [0, 0, 0, 0],
            "style_indexes": styles[offset] if offset < len(styles) else [],
            "paint_order": paint_orders[offset] if offset < len(paint_orders) else None,
            "is_stacking_context": node_index in stacking_contexts,
        }
    return layout_map


def _normalize_text(parts: list[str]) -> str:
    filtered = [_WHITESPACE_RE.sub(" ", part).strip() for part in parts if part and part.strip()]
    return " ".join(filtered).strip()


def _find_supported_computed_styles(cdp: Any, property_names: list[str]) -> list[str]:
    if not property_names:
        return []

    try:
        cdp.send(
            "DOMSnapshot.captureSnapshot",
            {
                "computedStyles": property_names,
                "includeDOMRects": False,
                "includePaintOrder": False,
            },
        )
        return property_names
    except Exception as exc:
        if "invalid CSS property" not in str(exc) or len(property_names) == 1:
            return []

    midpoint = len(property_names) // 2
    return _find_supported_computed_styles(cdp, property_names[:midpoint]) + _find_supported_computed_styles(
        cdp,
        property_names[midpoint:],
    )


def capture_layout_snapshot(cdp: Any, page: Any, computed_style_whitelist: list[str]) -> dict[str, Any]:
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    cdp.send("DOMSnapshot.enable")
    supported_computed_styles = _find_supported_computed_styles(cdp, computed_style_whitelist)
    snapshot = cdp.send(
        "DOMSnapshot.captureSnapshot",
        {
            "computedStyles": supported_computed_styles,
            "includeDOMRects": True,
            "includePaintOrder": True,
        },
    )
    document_metrics = page.evaluate(
        """
        () => {
          const root = document.scrollingElement || document.documentElement;
          return {
            url: window.location.href,
            title: document.title,
            viewport: { width: window.innerWidth, height: window.innerHeight },
            documentSize: { width: root.scrollWidth, height: root.scrollHeight },
            scroll: { x: window.scrollX, y: window.scrollY }
          };
        }
        """
    )
    return {
        "snapshot": snapshot,
        "document_metrics": document_metrics,
        "computed_style_whitelist": supported_computed_styles,
    }


def build_layout_nodes(snapshot_payload: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshot = snapshot_payload["snapshot"]
    document_metrics = snapshot_payload["document_metrics"]
    strings = snapshot.get("strings", [])
    documents = snapshot.get("documents", [])
    if not documents:
        return [], document_metrics

    document = documents[0]
    nodes = document.get("nodes") or {}
    node_types = nodes.get("nodeType") or []
    parent_indexes = nodes.get("parentIndex") or []
    backend_node_ids = nodes.get("backendNodeId") or []
    node_names = nodes.get("nodeName") or []
    node_values = nodes.get("nodeValue") or []
    attributes = nodes.get("attributes") or []
    text_values = nodes.get("textValue") or {}
    input_values = nodes.get("inputValue") or {}
    children_map = _build_children_map(parent_indexes)
    layout_map = _build_layout_map(document)

    retained_indexes: list[int] = []
    supplemental_media_metadata: dict[int, list[dict[str, Any]]] = {}

    for index, backend_node_id in enumerate(backend_node_ids):
        if index >= len(node_types) or node_types[index] != 1:
            continue

        tag_name = _decode_string(strings, node_names[index], "").lower()
        if not tag_name:
            continue

        if tag_name in MEDIA_METADATA_ONLY_TAGS:
            parent_index = parent_indexes[index] if index < len(parent_indexes) else -1
            if isinstance(parent_index, int) and parent_index >= 0:
                raw_attributes = attributes[index] if index < len(attributes) else []
                supplemental_media_metadata.setdefault(parent_index, []).append(
                    {
                        "tag": tag_name,
                        "attributes": _decode_attributes(strings, raw_attributes),
                    }
                )
            continue

        if tag_name in IGNORED_HTML_TAGS:
            continue

        if tag_name not in HTML_ELEMENTS_BY_ID:
            continue

        retained_indexes.append(index)

    retained_index_set = set(retained_indexes)

    @lru_cache(maxsize=None)
    def _direct_text(index: int) -> str:
        parts = []
        for child_index in children_map.get(index, []):
            if child_index >= len(node_types) or node_types[child_index] not in {3, 4}:
                continue
            raw_text = _decode_string(strings, node_values[child_index], "")
            if not raw_text:
                raw_text = _decode_sparse_value(strings, text_values, child_index)
            parts.append(raw_text)

        if not parts:
            current_tag = _decode_string(strings, node_names[index], "").lower()
            if current_tag in {"input", "textarea", "option"}:
                return _decode_sparse_value(strings, input_values, index)

        return _normalize_text(parts)

    def _nearest_retained_parent(index: int) -> int | None:
        current = parent_indexes[index] if index < len(parent_indexes) else -1
        while isinstance(current, int) and current >= 0:
            if current in retained_index_set:
                return current
            current = parent_indexes[current] if current < len(parent_indexes) else -1
        return None

    def _build_xpath(index: int) -> str:
        segments: list[str] = []
        current = index
        while isinstance(current, int) and current >= 0:
            if current >= len(node_types) or node_types[current] != 1:
                current = parent_indexes[current] if current < len(parent_indexes) else -1
                continue

            tag_name = _decode_string(strings, node_names[current], "").lower()
            if not tag_name:
                break

            parent_index = parent_indexes[current] if current < len(parent_indexes) else -1
            sibling_position = 1
            if isinstance(parent_index, int) and parent_index >= 0:
                same_tag_siblings = [
                    child_index
                    for child_index in children_map.get(parent_index, [])
                    if child_index < len(node_types)
                    and node_types[child_index] == 1
                    and _decode_string(strings, node_names[child_index], "").lower() == tag_name
                ]
                sibling_position = same_tag_siblings.index(current) + 1 if current in same_tag_siblings else 1

            segments.append(f"{tag_name}[{sibling_position}]")
            current = parent_index

        return "/" + "/".join(reversed(segments))

    raw_nodes: list[dict[str, Any]] = []
    for document_order, source_index in enumerate(retained_indexes, start=1):
        tag_name = _decode_string(strings, node_names[source_index], "").lower()
        attrs = _decode_attributes(strings, attributes[source_index] if source_index < len(attributes) else [])
        layout_entry = layout_map.get(source_index, {})
        bounds = layout_entry.get("bounds", [0, 0, 0, 0])
        style_indexes = layout_entry.get("style_indexes", [])
        computed_styles = _decode_computed_styles(
            strings,
            snapshot_payload.get("computed_style_whitelist", []),
            style_indexes,
        )

        direct_text = _direct_text(source_index)

        raw_nodes.append(
            {
                "source_index": source_index,
                "backend_node_id": backend_node_ids[source_index],
                "parent_source_index": _nearest_retained_parent(source_index),
                "document_order": document_order,
                "paint_order": layout_entry.get("paint_order"),
                "is_out_of_scope": HTML_ELEMENTS_BY_ID[tag_name].scope_group.value == "out_of_scope_visible",
                "identity": {
                    "tag": tag_name,
                    "node_name": tag_name.upper(),
                    "id": attrs.get("id"),
                    "name": attrs.get("name"),
                    "role": attrs.get("role"),
                    "class_list": [value for value in attrs.get("class", "").split() if value],
                    "data_attributes": {
                        key: value for key, value in attrs.items() if key.startswith("data-")
                    }
                    or None,
                    "attributes": attrs,
                    "selector_hint": _build_selector_hint(tag_name, attrs, source_index),
                    "xpath": _build_xpath(source_index),
                    "related_media": supplemental_media_metadata.get(source_index) or None,
                },
                "layout": {
                    "x": bounds[0] if len(bounds) > 0 else 0,
                    "y": bounds[1] if len(bounds) > 1 else 0,
                    "width": bounds[2] if len(bounds) > 2 else 0,
                    "height": bounds[3] if len(bounds) > 3 else 0,
                    "absolute_bounds": {
                        "left": bounds[0] if len(bounds) > 0 else 0,
                        "top": bounds[1] if len(bounds) > 1 else 0,
                        "right": (bounds[0] + bounds[2]) if len(bounds) > 2 else 0,
                        "bottom": (bounds[1] + bounds[3]) if len(bounds) > 3 else 0,
                    },
                },
                "styles": {
                    "computed": computed_styles,
                },
                "text": direct_text or None,
                "flags": {
                    "is_out_of_scope": HTML_ELEMENTS_BY_ID[tag_name].scope_group.value == "out_of_scope_visible",
                    "is_visible": _is_layout_visible(bounds),
                    "is_stacking_context": bool(layout_entry.get("is_stacking_context", False)),
                },
            }
        )

    return raw_nodes, document_metrics


def _decode_computed_styles(
    strings: list[str],
    property_names: list[str],
    style_indexes: list[int],
) -> list[str]:
    decoded: list[str] = []
    for property_name, value_index in zip(property_names, style_indexes):
        if not isinstance(value_index, int):
            continue
        value = _decode_string(strings, value_index, "")
        if value in ("", "initial", "auto", "normal", "none", "0px"):
            continue
        decoded.append(f"{property_name}:{value}")
    return decoded


def _build_selector_hint(tag_name: str, attrs: dict[str, str], index: int) -> str:
    if attrs.get("id"):
        return f"{tag_name}#{attrs['id']}"
    if attrs.get("class"):
        return f"{tag_name}.{attrs['class'].split()[0]}"
    return f"{tag_name}[data-node-index='{index}']"


def _is_layout_visible(bounds: list[float]) -> bool:
    if len(bounds) < 4:
        return False
    return bounds[2] > 0 and bounds[3] > 0
