from __future__ import annotations

from typing import Any

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.enums.scope.css_properties import getAllPropertyNames
from engine.domain.models.color import unique_colors
from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.element import Element, Property
from engine.domain.models.session import Session
from engine.domain.utils.parsers import (
    flatten_list,
    get_value,
    resolve_index_map,
    resolve_pairs,
    resolve_value,
)
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_capture(session: Session) -> bool:
    try:
        candidates = session.find_by_suffix("before", ("html",))
        return len(candidates) == 1 and candidates[0].exists()
    except (FileNotFoundError, RuntimeError, ValueError, OSError):
        return False


CONTRACT = StageContract(
    name="capture_original_state",
    requires=(
        context_value(K.PAGE_BUILDER, PageBuilder),
        context_value(K.SESSION, Session, validator=_session_ready_for_capture),
    ),
    produces=(
        context_value(K.DOM_TREE, Element),
        context_value(K.COLOR_SCHEME, ColorScheme),
        context_value(K.DERIVED_RAW_SNAPSHOT_METADATA, dict),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    session = context.get(K.SESSION)
    if context.error or context.has(K.DOM_TREE):
        return context

    page_builder = context.get(K.PAGE_BUILDER)
    whitelist_styles = list(getAllPropertyNames())
    before_screenshot = session.get_path("before.png", "artifacts", "png")

    context.trace.add_stage_event(
        CONTRACT.name,
        "start",
        {
            "output_image": str(before_screenshot),
            "computed_style_count": len(whitelist_styles),
        },
    )

    screenshot_path = page_builder.capture_full_page_screenshot(output_path=before_screenshot)
    raw_snapshot = page_builder.extract_raw_snapshot(whitelist_styles)
    dom_tree = _assemble_domain_tree(raw_snapshot, whitelist_styles)
    if dom_tree is None:
        return context.set_error("DOMSnapshot no contiene un arbol DOM valido.")

    colors = unique_colors(color for element in dom_tree.iter_dfs() for color in element.all_colors)
    color_scheme = ColorScheme.build(colors)
    metadata = _snapshot_metadata(raw_snapshot, dom_tree)

    context.set(K.DOM_TREE, dom_tree)
    context.set(K.COLOR_SCHEME, color_scheme)
    context.set(K.DERIVED_RAW_SNAPSHOT_METADATA, metadata)

    context.trace.add_step(
        "dom.capture_done",
        {
            "screenshot_path": screenshot_path,
            "node_count": metadata["node_count"],
            "observed_color_count": len(color_scheme),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "node_count": metadata["node_count"],
            "observed_color_count": len(color_scheme),
        },
    )
    return context


def _assemble_domain_tree(
    snapshot: dict[str, Any],
    whitelist_styles: list[str],
) -> Element | None:
    strings: list[str] = resolve_value(snapshot, "strings", [])
    nodes_dict: dict[str, Any] = resolve_value(snapshot, "documents.0.nodes", {})
    layout_dict: dict[str, Any] = resolve_value(snapshot, "documents.0.layout", {})
    text_boxes_dict: dict[str, Any] = resolve_value(snapshot, "documents.0.textBoxes", {})

    node_arrays = list(
        flatten_list(
            nodes_dict,
            ["nodeName", "nodeType", "backendNodeId", "parentIndex", "nodeValue"],
        )
    )
    node_names = get_value(node_arrays, 0, [])
    node_types = get_value(node_arrays, 1, [])
    backend_node_ids = get_value(node_arrays, 2, [])
    parent_indices = get_value(node_arrays, 3, [])
    node_values = get_value(node_arrays, 4, [])

    layout_arrays = list(flatten_list(layout_dict, ["nodeIndex", "bounds", "styles"]))
    layout_node_indices = get_value(layout_arrays, 0, [])
    layout_bounds = get_value(layout_arrays, 1, [])
    layout_styles = get_value(layout_arrays, 2, [])

    text_box_arrays = list(flatten_list(text_boxes_dict, ["layoutIndex"]))
    text_box_layout_indices = get_value(text_box_arrays, 0, [])
    layout_lookup = resolve_index_map(layout_node_indices)
    text_box_set = set(text_box_layout_indices)

    elements_by_node_index: dict[int, Element] = {}
    parent_linkage_records: list[tuple[int, int]] = []
    root: Element | None = None

    for node_index, tag_ref in enumerate(node_names):
        node_type = int(get_value(node_types, node_index, -1))
        if node_type not in (1, 3, 9):
            continue

        tag_name = _resolve_string(strings, tag_ref).lower()
        if node_type == 3:
            tag_name = "#text"

        backend_node_id = int(get_value(backend_node_ids, node_index, 0) or 0)
        element = Element(
            backend_node_id=backend_node_id,
            node_id=backend_node_id or node_index,
            tag_name=tag_name,
            node_type=node_type,
            is_text_node=node_type == 3,
        )

        layout_position = get_value(layout_lookup, node_index)
        if layout_position is not None:
            _hydrate_layout(element, layout_bounds, int(layout_position))
            _hydrate_properties(
                element,
                strings,
                whitelist_styles,
                get_value(layout_styles, int(layout_position), []),
            )
            if int(layout_position) in text_box_set:
                element.is_text_node = True

        _hydrate_common_attributes(element)
        if node_type == 3 and not element.properties:
            text_value = _resolve_string(strings, get_value(node_values, node_index, ""))
            if text_value:
                element.properties.append(Property(name="text", value=text_value))

        elements_by_node_index[node_index] = element
        raw_parent_index = get_value(parent_indices, node_index, -1)
        parent_index = int(raw_parent_index) if raw_parent_index is not None else -1
        parent_linkage_records.append((node_index, parent_index))

    for node_index, parent_index in parent_linkage_records:
        child = elements_by_node_index[node_index]
        parent = elements_by_node_index.get(parent_index)
        if parent is None:
            if root is None:
                root = child
            continue
        parent.add_child(child)

    return root


def _hydrate_layout(element: Element, layout_bounds: list[Any], layout_position: int) -> None:
    bounds = get_value(layout_bounds, layout_position)
    if isinstance(bounds, list) and len(bounds) >= 4:
        element.x, element.y, element.width, element.height = (
            float(bounds[0]),
            float(bounds[1]),
            float(bounds[2]),
            float(bounds[3]),
        )
        return

    offset = layout_position * 4
    element.x = float(get_value(layout_bounds, offset, 0) or 0)
    element.y = float(get_value(layout_bounds, offset + 1, 0) or 0)
    element.width = float(get_value(layout_bounds, offset + 2, 0) or 0)
    element.height = float(get_value(layout_bounds, offset + 3, 0) or 0)


def _hydrate_properties(
    element: Element,
    strings: list[str],
    whitelist_styles: list[str],
    computed_style_indices: list[Any],
) -> None:
    for property_name, string_index in resolve_pairs(whitelist_styles, computed_style_indices):
        if string_index is None or int(string_index) == -1:
            continue
        value = _resolve_string(strings, string_index)
        if value:
            element.properties.append(Property(name=str(property_name), value=value))


def _hydrate_common_attributes(element: Element) -> None:
    property_values = {prop.name: prop.value for prop in element.properties}
    element.font_size = property_values.get("font-size")
    element.font_weight = property_values.get("font-weight")


def _resolve_string(strings: list[str], value: Any) -> str:
    if isinstance(value, int):
        return str(get_value(strings, value, ""))
    return str(value or "")


def _snapshot_metadata(snapshot: dict[str, Any], root: Element) -> dict[str, Any]:
    documents = resolve_value(snapshot, "documents", [])
    return {
        "document_count": len(documents) if hasattr(documents, "__len__") else 0,
        "node_count": sum(1 for _ in root.iter_dfs()),
    }
