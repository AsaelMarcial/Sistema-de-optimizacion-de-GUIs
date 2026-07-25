from __future__ import annotations

from collections import defaultdict

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.data.scope_css import CSSPROPERTIES, collect_longhands
from engine.domain.models.color_scheme import Color, ColorScheme
from engine.domain.models.element import Attribute, Element, Property
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.domain.utils.parsers import has_multiplevalues, matches_default_value

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
            and all(element.tag_name for element in elements)
            and all(isinstance(element.backend_node_id, int) for element in elements)
            and all(element.backend_node_id != 0 for element in elements)
            and all(isinstance(element.node_id, int) for element in elements)
            and all(element.node_id >= 0 for element in elements)
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
    
    color_scheme = ColorScheme()
    snapshot = page_builder.extract_raw_snapshot(whitelist_styles)

    strings = snapshot.get("strings", [])
    documents = snapshot.get("documents", [])
    document = documents[0] if documents else {}
    nodes = document.get("nodes", {})
    layout = document.get("layout", {})

    created_elements: dict[int, Element] = {}
    siblings: dict[int, list[int]] = defaultdict(list)
    root: Element | None = None

    for i in range(len(nodes["backendNodeId"])):

        if nodes["nodeType"][i] not in (1, 3) or nodes["backendNodeId"][i] is None:
            continue

        node = page_builder.resolve_backend_node_id(nodes["backendNodeId"][i]) 
        node_id = node.get("nodeId")

        element = Element(
            backend_node_id=nodes["backendNodeId"][i],
            node_id=node_id,
            tag_name=str(strings[nodes["nodeName"][i]]).lower(),
            node_type=nodes["nodeType"][i],
            parent_backend_node_id=nodes["backendNodeId"][nodes["parentIndex"][i]] if str(strings[nodes["nodeName"][i]]).lower() != "body" else -1,
        )

        if element.tag_name == "body":
            root = element

        for name, value in zip(nodes["attributes"][i][::2], nodes["attributes"][i][1::2]):
            if str(strings[name]) in _IMAGE_ATTRIBUTES:
                element.attributes.append(
                    Attribute(
                        name=str(strings[name]),
                        value=str(strings[value]),
                    )
                )

        created_elements[element.backend_node_id] = element
        siblings[element.parent_backend_node_id].append(element.backend_node_id)

        if i in layout["nodeIndex"]:
            layout_index = layout["nodeIndex"].index(i)
            element.x, element.y, element.width, element.height = layout["bounds"][layout_index]

            for name, value in zip(whitelist_styles, layout["styles"][layout_index]):
                if value is None:
                    continue

                element.properties.append(
                    Property(
                        name=name,
                        before_value=str(strings[value]),
                    )
                )

    if root is None:
        return context.set_error("DOMSnapshot no contiene un nodo body valido.")

    _attach_children(root, siblings, created_elements)

    depth_by_backend_node_id: dict[int, int] = {-1: -1}
    for element in root.iter_dfs():
        element.depth = depth_by_backend_node_id.get(element.parent_backend_node_id, -1) + 1
        depth_by_backend_node_id[element.backend_node_id] = element.depth
        _filter_properties(element)
        for property_model in element.properties:
            property_model.has_color = _register_colors(property_model.before_value, color_scheme)

    context.set(K.DOM_TREE, root)
    context.set(K.COLOR_SCHEME, color_scheme)

    context.trace.add_step(
        "dom.capture_done",
        {
            "screenshot_path": screenshot_path,
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
        if child.x is None or child.y is None or child.height is None or child.width is None:
            continue
        parent.add_child(child)
        _attach_children(child, siblings, elements)

SVG_PAINT_TAGS = {"svg", "circle", "rect", "ellipse", "line", "polyline", "polygon", "path"}

def _filter_properties(element: Element) -> None:
    # 1. Eliminar valores predeterminados y propiedades redundantes.
    for css_property in tuple(element.properties):
        property_name = css_property.name
        current_property = element.property(property_name)

        if current_property is None:
            continue

        property_data = CSSPROPERTIES[property_name]

        if matches_default_value(
            current_property.before_value,
            property_data.default_value,
        ):
            element.remove_property(property_name)

            for longhand_name in collect_longhands(property_name):
                element.remove_property(longhand_name)

            continue

        if property_data.longhands is None:
            continue

        longhands = tuple(
            longhand_name
            for longhand_name in property_data.longhands
            if element.property(longhand_name) is not None
        )

        if not longhands:
            continue

        if len(longhands) == 1:
            element.remove_property(property_name)
            continue

    # 2. Eliminar propiedades SVG que no aplican al elemento.
    if element.tag_name not in SVG_PAINT_TAGS:
        for property_name in ("fill", "stroke"):
            element.remove_property(property_name)

    # 3. Eliminar colores reemplazados por imágenes.
    if element.property("background-image") is not None:
        element.remove_property("background-color")

    if element.property("border-image-source") is not None:
        for property_name in (
            "border",
            "border-color",
            "border-block-color",
            "border-inline-color",
        ):
            element.remove_property(property_name)

    # 5. Eliminar de los hijos de texto las propiedades repetidas
    # respecto al elemento que las contiene.
    if element.has_text:
        for child in element.children:
            if child.tag_name != "#text":
                continue

            for text_property in tuple(child.properties):
                element_property = element.property(text_property.name)

                if (
                    element_property is None
                    or element_property.before_value == text_property.before_value
                ):
                    child.remove_property(text_property.name)

    # 6. Eliminar propiedades tipográficas de elementos sin texto.
    if not element.has_text:
        for property_name in ("font-size", "font-weight"):
            element.remove_property(property_name)

def _register_colors(value: str, color_scheme: ColorScheme) -> bool:
    found_color = False
    start = 0
    while start < len(value):
        match = Color.match(value, start=start)
        if match is None:
            start += 1
            continue

        if match.color.alpha(nans=False) > 0:
            found_color = True
            color_scheme.add_color(match.color)
            
        end = int(getattr(match, "end", start + 1))
        start = max(end, start + 1)
    return found_color
