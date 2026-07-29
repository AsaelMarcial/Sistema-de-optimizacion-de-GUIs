from __future__ import annotations

from collections import defaultdict

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.data.scope_css import CSSPROPERTIES
from engine.domain.data.scope_html_elements import get_html_element_category
from engine.domain.models.color_scheme import Color, ColorScheme
from engine.domain.models.element import Attribute, Element, Property
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.domain.utils.parsers import get_colors, is_gradient, is_url_image, get_file_name_and_suffix
import tinycss2


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
    if context.error or context.has(K.DOM_TREE):
        return context
    
    session = context.get(K.SESSION)
    page_builder = context.get(K.PAGE_BUILDER)
    color_scheme = ColorScheme()
    whitelist_styles = list(CSSPROPERTIES.keys())
    before_screenshot = session.get_path("before.png", "artifacts", "png")
    screenshot_path = page_builder.capture_fullpage_screenshot(output_path=before_screenshot)
    
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
            category=get_html_element_category(str(strings[nodes["nodeName"][i]]).lower()),
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
        image_references = element.image_references()
        if image_references:
            image_property = image_references[0]
            _, suffix = get_file_name_and_suffix(image_property)
            if suffix.lower() == "svg":
                element.category = "decoration"
        
    if root is None:
        return context.set_error("DOMSnapshot no contiene un nodo body valido.")

    _attach_children(root, siblings, created_elements)

    depth_by_backend_node_id: dict[int, int] = {-1: -1}
    for element in root.iter_dfs():
        element.depth = depth_by_backend_node_id.get(element.parent_backend_node_id, -1) + 1
        depth_by_backend_node_id[element.backend_node_id] = element.depth
        css_text = ""
        if not element.tag_name.startswith("#") and not element.tag_name.startswith("::"):
            matched_styles = page_builder.get_matched_styles(element.node_id)
            for key, info in matched_styles.items():
                match key:
                    case "matchedCSSRules":
                        if not info:
                            continue
                        for rulematch in info:
                            rule = rulematch.get("rule") or {}
                            if rule.get("styleSheetId") is not None and rule.get("origin") == "regular":
                                style = rule.get("style") or {}
                                if style.get("cssText") is not None:
                                    css_text += "\n" + str(style.get("cssText"))
                    case "inlineStyle":
                        if not info:
                            continue
                        if info.get("cssText") is not None and info.get("cssText") != "":
                            css_text += "\n" + str(info.get("cssText"))
                    case "attributesStyle":
                        if not info:
                            continue                       
                        for property in info.get("cssProperties"):
                            css_text += "\n" + str(property.get("name"))+ ": " + str(property.get("value"))
                    case _:
                            continue

        _filter_properties(element, css_text)
        #print("->>>>>"+element.tag_name)
        #for property in element.properties:
        #   print(str(property.name) + ": " + str(property.before_value) + " -> " + str(property.after_value)+ " -> " + str(property.token_value))
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

def _filter_properties(element: Element, css_text: str) -> None:
    if css_text != "" and not element.tag_name.startswith("#") and not element.tag_name.startswith("::"):
        raw_nodes = tinycss2.parse_declaration_list(css_text, skip_comments=True)
        found_properties = set()
        
        for node in raw_nodes:
            if node.type == 'declaration':
                name = node.name.strip().lower()
                raw_value = tinycss2.serialize(node.value).lower()
                found_properties.add((name, _color_signature(raw_value)))

        not_matched=[]
        if element.tag_name not in SVG_PAINT_TAGS:
            for property_name in ("fill", "stroke"):
                element.remove_property(property_name)   

        for property in element.properties:
            search_name = property.name.strip().lower()
            search_colors = _color_signature(property.before_value)

            if (search_name, search_colors) not in found_properties:
                if _should_keep_unmatched_property(element, property):
                    continue
                else:
                    not_matched.append(property)

        for name in [property.name for property in not_matched]:
            element.remove_property(name)  

    elif css_text == "" or element.tag_name.startswith("#") or element.tag_name.startswith("::"):
        for name in [property.name for property in element.properties]:
            element.remove_property(name) 

   
def _should_keep_unmatched_property(element: Element, property: Property) -> bool:
    property_name = property.name.strip().lower()
    return (
        (property_name in ("font-weight", "font-size","color") and element.has_text)
        or is_url_image(property.before_value)
        or is_gradient(property.before_value)
        or (
            element.tag_name == "body"
            and property_name in ("color", "background-color")
        )
        or (property_name in ("fill", "stroke") and element.category == "decoration")
    )


def _color_signature(value: str) -> tuple[str, ...]:
    colors = get_colors(value)
    if not colors:
        return ()

    return tuple(
        color.convert("srgb").to_string(
            comma=True,
            alpha=True,
            precision=0,
        )
        for _raw_value, color in colors
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
            found_color = True
            color_scheme.add_color(match.color.set("alpha", 1))
            
        end = int(getattr(match, "end", start + 1))
        start = max(end, start + 1)
    return found_color
