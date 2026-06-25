from __future__ import annotations

from collections import defaultdict

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.data.scope_css import CSSPROPERTIES, collect_longhands, get_shorthand
from engine.domain.models.color_scheme import Color, ColorScheme
from engine.domain.models.element import Attribute, Element, Property
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.domain.utils.parsers import has_multiplevalues

_IMAGE_ATTRIBUTES = {
    "src",
    "srcset",
    "href",
    "xlink:href",
    "poster",
    "data",
}

def _session_ready_for_capture(session: Session) -> bool:
    try:
        candidates = session.find_by_suffix("before", ("html",))
        return len(candidates) == 1 and candidates[0].exists()
    except (FileNotFoundError, RuntimeError, ValueError, OSError):
        return False


def _dom_tree_ready(root: Element) -> bool:
    try:
        elements = tuple(root.iter_dfs())
        return (
            root.tag_name == "body"
            and bool(elements)
            and root.parent_backend_node_id == -1
            and isinstance(root.backend_node_id, int)
            and root.backend_node_id != 0
            and all(element.tag_name for element in elements)
            and all(isinstance(element.backend_node_id, int) for element in elements)
            and all(element.backend_node_id != 0 for element in elements)
            and all(isinstance(element.node_id, int) for element in elements)
            and all(element.node_id > 0 for element in elements)
            and len({element.node_id for element in elements}) == len(elements)
        )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False


def _color_scheme_ready(color_scheme: ColorScheme) -> bool:
    try:
        return isinstance(color_scheme.get_colors(), dict)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False


CONTRACT = StageContract(
    name="capture_original_state",
    requires=(
        context_value(K.PAGE_BUILDER, PageBuilder),
        context_value(K.SESSION, Session, validator=_session_ready_for_capture),
    ),
    produces=(
        context_value(K.DOM_TREE, Element, validator=_dom_tree_ready),
        context_value(K.COLOR_SCHEME, ColorScheme, validator=_color_scheme_ready),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    session = context.get(K.SESSION)
    if context.error or context.has(K.DOM_TREE):
        return context

    page_builder = context.get(K.PAGE_BUILDER)
    whitelist_styles = list(CSSPROPERTIES.keys())
    before_screenshot = session.get_path("before.png", "artifacts", "png")
    screenshot_path = page_builder.capture_fullpage_screenshot(output_path=before_screenshot)
  
    context.trace.add_stage_event(
        CONTRACT.name,
        "start",
        {
            "computed_style_count": len(whitelist_styles),
        },
    )
    
    color_scheme = ColorScheme()
    snapshot = page_builder.extract_raw_snapshot(whitelist_styles)

    strings = snapshot.get("strings", [])
    documents = snapshot.get("documents", [])
    document = documents[0] if documents else {}
    nodes = document.get("nodes", {})
    layout = document.get("layout", {})

    node_names = nodes.get("nodeName", [])
    node_types = nodes.get("nodeType", [])
    backend_node_ids = nodes.get("backendNodeId", [])
    parent_indices = nodes.get("parentIndex", [])
    node_values = nodes.get("nodeValue", [])
    node_attributes = nodes.get("attributes", [])
    total_nodes = len(backend_node_ids)

    layout_node_indices = layout.get("nodeIndex", [])
    layout_bounds = layout.get("bounds", [])
    layout_styles = layout.get("styles", [])

    layout_map = dict(zip(layout_node_indices, layout_bounds))
    layout_styles_map = dict(zip(layout_node_indices, layout_styles))

    created_elements: dict[int, Element] = {}
    siblings: dict[int, list[int]] = defaultdict(list)
    root: Element | None = None

    for i in range(total_nodes):
        
        node_type = node_types[i] if i < len(node_types) else -1
        if node_type not in (1, 3):
            continue

        if node_type == 3 and not str(strings[node_values[i]]).strip():
            continue

        backend_node_id = int(backend_node_ids[i]) if i < len(backend_node_ids) else None
        node_id = None
        parent_index = parent_indices[i]
        parent_backend_node_id = int(backend_node_ids[parent_index]) if parent_index >= 0 else -1
        tag_name = "#text" if node_type == 3 else str(strings[node_names[i]]).lower()

        if backend_node_id is not None:
            node = page_builder.resolve_backend_node_id(backend_node_id)
            node_id = node.get("nodeId")

        element = Element(
            backend_node_id=backend_node_id,
            node_id=node_id,
            tag_name=tag_name,
            node_type=node_type,
            parent_backend_node_id=parent_backend_node_id,
        )

        for name_idx, value_idx in zip(node_attributes[i][::2], node_attributes[i][1::2]):
            if str(strings[name_idx]) in _IMAGE_ATTRIBUTES:
                element.attributes.append(
                    Attribute(
                        name=str(strings[name_idx]),
                        value=str(strings[value_idx]),
                    )
                )

        if element.tag_name == "body":
            root = element
        created_elements[backend_node_id] = element
        siblings[parent_backend_node_id].append(backend_node_id)

        if i in layout_map:
            bounds = layout_map[i]
            element.x, element.y, element.width, element.height = (
                float(bounds[0]),
                float(bounds[1]),
                float(bounds[2]),
                float(bounds[3]),
            )

        if i in layout_styles_map:
            computed_style_values = {
                property_name: str(strings[string_idx])
                for property_name, string_idx in zip(whitelist_styles, layout_styles_map[i])
                if string_idx is not None
            }

            for property_name, property_value in computed_style_values.items():
                element.properties.append(
                    Property(
                        name=property_name,
                        value=property_value,
                    )
                )

    if root is None:
        return context.set_error("DOMSnapshot no contiene un nodo body valido.")

    root.parent_backend_node_id = -1
    _attach_children(root, siblings, created_elements)

    for element in root.iter_dfs():
        _filter_properties(element, root)
        for property_model in element.properties:
            property_model.has_color = _register_colors(property_model.value, color_scheme)

    page_builder.set_effective_value(root.node_id, "background-color", "rgb(0, 0, 0)")
    page_builder.set_color_scheme()
    after_screenshot = session.get_path("after.png", "artifacts", "png")
    after_screenshot_path = page_builder.capture_fullpage_screenshot(output_path=after_screenshot)

    context.set(K.DOM_TREE, root)
    context.set(K.COLOR_SCHEME, color_scheme)

    context.trace.add_step(
        "dom.capture_done",
        {
            "screenshot_path": screenshot_path,
            "after_screenshot_path": after_screenshot_path,
            "observed_color_count": len(color_scheme.get_colors()),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "observed_color_count": len(color_scheme.get_colors()),
        },
    )
    return context

def _attach_children(
    parent: Element,
    siblings: dict[int, list[int]],
    elements: dict[int, Element],
) -> None:
    for child_backend_node_id in siblings.get(parent.backend_node_id, ()):
        child = elements[child_backend_node_id]
        parent.add_child(child)
        _attach_children(child, siblings, elements)

SVG_PAINT_TAGS = {"svg", "circle", "rect", "ellipse", "line", "polyline", "polygon", "path"}
SVG_SHAPE_TAGS = SVG_PAINT_TAGS - {"svg"}


def _filter_properties(element: Element, root: Element) -> None:
    for property_model in tuple(element.properties):
        if element.property(property_model.name) is None:
            continue

        property_data = CSSPROPERTIES[property_model.name]
        if _matches_default_value(
            property_model.value,
            property_data.default_value,
        ):
            element.remove_property(property_model.name)
            for longhand in collect_longhands(property_model.name):
                element.remove_property(longhand)
            continue

        if get_shorthand(property_model.name) is not None or property_data.longhands is None:
            continue

        element.remove_property(property_model.name)
        for intermediate_name in property_data.longhands:
            intermediate = element.property(intermediate_name)
            if intermediate is None:
                continue
            for longhand_name in CSSPROPERTIES[intermediate.name].longhands or ():
                longhand = element.property(longhand_name)
                if longhand is not None and longhand.value == intermediate.value:
                    element.remove_property(longhand.name)

    if element.property("list-style-image") is not None:
        for descendant in element.iter_dfs():
            if descendant.property("list-style-image") is not None and descendant != element and descendant.property("list-style-image").value == element.property("list-style-image").value:
                descendant.remove_property("list-style-image")

    if element.tag_name not in SVG_PAINT_TAGS:
        element.remove_property("fill")
        element.remove_property("stroke")

    if element.tag_name == "svg":
        stroke = element.property("stroke")
        fill = element.property("fill")
        if stroke is not None or fill is not None:
            for descendant in element.iter_dfs():
                if descendant is element or descendant.tag_name not in SVG_SHAPE_TAGS:
                    continue

                descendant_stroke = descendant.property("stroke")
                if stroke is not None and descendant_stroke is not None and descendant_stroke.value == stroke.value:
                    descendant.remove_property("stroke")

                descendant_fill = descendant.property("fill")
                if fill is not None and descendant_fill is not None and descendant_fill.value == fill.value:
                    descendant.remove_property("fill")

    if not any(child.tag_name == "#text" for child in element.children):
        element.remove_property("color")

    if element.property("background-image") is not None:
        element.remove_property("background-color")

    if element.property("border-image-source") is not None:
        element.remove_property("border")
        element.remove_property("border-color")
        element.remove_property("border-bottom-color")
        element.remove_property("border-left-color")
        element.remove_property("border-right-color")
        element.remove_property("border-top-color")

    if element.property("border-color") is not None and has_multiplevalues(element.property("border-color").value):
        element.remove_property("border-color")

    if element.tag_name == "#text":
        parent = root.find_by_backend_node_id(element.parent_backend_node_id)
        if parent is not None:
            for property_model in tuple(element.properties):
                parent_property = parent.property(property_model.name)
                if parent_property is not None and parent_property.value == property_model.value:
                    element.remove_property(property_model.name)

def _matches_default_value(property_value: str, default_value: object) -> bool:
    if default_value is None:
        return False

    default_values = (default_value,) if isinstance(default_value, str) else tuple(default_value)
    normalized_property_value = " ".join(str(property_value).lower().split())
    return any(
        normalized_default in normalized_property_value
        for value in default_values
        if value is not None and (normalized_default := " ".join(str(value).lower().split()))
    )

def _register_colors(value: str, color_scheme: ColorScheme) -> bool:
    found_color = False
    start = 0
    while start < len(value):
        match = Color.match(value, start=start)
        if match is None:
            start += 1
            continue

        if match.color.alpha(nans=False) > 0:
            stored_color = color_scheme.add_color(match.color)
            found_color = stored_color is not None or found_color
        end = int(getattr(match, "end", start + 1))
        start = max(end, start + 1)
    return found_color
