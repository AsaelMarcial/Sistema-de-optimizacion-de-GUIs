from __future__ import annotations

from collections import defaultdict

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.source_code_handler.local_asset_rewriter import extract_reference_candidates
from engine.domain.data.scope_css import CSSPROPERTIES, get_default_values
from engine.domain.data.scope_html_elements import get_html_element_category
from engine.domain.models.color_scheme import Color, ColorScheme
from engine.domain.models.element import Element, Property
from engine.pipeline.context import PipelineContext
from engine.pipeline.glow_runtime import (
    glow_flow,
    glow_task,
)
from engine.domain.utils.parsers import get_colors, matches_default_value
import tinycss2
from pathlib import Path
from prefect.states import Completed, Failed, State, get_state_exception


_IMAGE_ATTRIBUTES = {
    "src",
    "srcset",
    "data-src",
    "data-srcset",
    "href",
    "xlink:href",
    "poster",
    "data",
}


@glow_task
def _dom_tree_ready(root: Element | None) -> State:
    if root is None:
        raise get_state_exception(Failed(message="No se genero arbol DOM."))

    elements = tuple(root.iter_dfs())
    if (
        root.tag_name == "body"
        and bool(elements)
        and root.parent_backend_node_id == -1
        and all(element.tag_name for element in elements)
        and all(isinstance(element.backend_node_id, int) for element in elements)
        and all(element.backend_node_id != 0 for element in elements)
        and all(isinstance(element.node_id, int) for element in elements)
        and all(element.node_id >= 0 for element in elements)
    ):
        return Completed(message="El arbol DOM esta listo.")
    raise get_state_exception(Failed(message="El arbol DOM no paso validacion."))


@glow_task
def _color_scheme_ready(color_scheme: ColorScheme | None) -> State:
    if color_scheme is None:
        raise get_state_exception(Failed(message="No se genero ColorScheme."))

    if isinstance(color_scheme.get_colors(), dict):
        return Completed(message="ColorScheme esta listo.")
    raise get_state_exception(Failed(message="ColorScheme no paso validacion."))


@glow_task
def _capture_original_state_failed(message: str) -> State:
    raise get_state_exception(Failed(message=message))


@glow_flow
def capture_original_state(context: PipelineContext):
    session = context.session
    page_builder = context.page_builder
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

        tag_name = str(strings[nodes["nodeName"][i]]).strip().lower()

        element = Element(
            backend_node_id=nodes["backendNodeId"][i],
            node_id=node_id,
            tag_name=tag_name,
            node_type=nodes["nodeType"][i],
            category=get_html_element_category(tag_name),
            parent_backend_node_id=nodes["backendNodeId"][nodes["parentIndex"][i]] if tag_name != "body" else -1,
        )

        for name, value in zip(nodes["attributes"][i][::2], nodes["attributes"][i][1::2]):
            attribute_name = str(strings[name]).strip().casefold()
            if attribute_name in _IMAGE_ATTRIBUTES:
                element.properties.append(
                    Property(
                        name=attribute_name,
                        before_value=str(strings[value]),
                        type="attribute",
                        is_defined=True,
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
        for image_reference in element.properties:
            candidates = extract_reference_candidates(
                image_reference.current_value,
                attribute_name=(
                    image_reference.name
                    if image_reference.type == "attribute"
                    else None
                ),
            )
            if not candidates:
                continue

            for candidate in candidates:
                source = session.register_source(candidate)
                source.add_used_by(element.backend_node_id)
                if image_reference.image_source is None:
                    image_reference.image_source = source

                if (
                    source.type == "local"
                    and source.load_status == "loaded"
                    and isinstance(source.source_name, Path)
                    and any(
                        svg_path.stem.lower() == source.source_name.stem.lower()
                        for svg_path in session.get_by_type(".svg")
                    )
                ):
                    image_reference.image_source = source
                    element.category = "decoration"
                    break

        if element.tag_name == "body":
            root = element
        
    if root is None:
        _capture_original_state_failed("DOMSnapshot no contiene un nodo body valido.")

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
                        css_text += "\n" + "matchedCSSRules"
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
                            css_text += "\n" + "inlineStyle"
                            css_text += "\n" + str(info.get("cssText"))
                    case "attributesStyle":
                        if not info:
                            continue
                        css_text += "\n" + "attributesStyle"
                        for property in info.get("cssProperties"):
                            css_text += "\n" + str(property.get("name"))+ ": " + str(property.get("value"))
                    case "inherited":
                        if not info:
                            continue
                        css_text += "\n" + "inherited"
                        for inherited_entry in info:
                            inline_style = inherited_entry.get("inlineStyle") or {}
                            if inline_style.get("cssText") is not None and inline_style.get("cssText") != "":
                                css_text += "\n" + str(inline_style.get("cssText"))

                            for rulematch in inherited_entry.get("matchedCSSRules") or []:
                                rule = rulematch.get("rule") or {}
                                if rule.get("styleSheetId") is not None and rule.get("origin") == "regular":
                                    style = rule.get("style") or {}
                                    if style.get("cssText") is not None:
                                        css_text += "\n" + str(style.get("cssText"))
                    case _:
                            continue
        _filter_properties(element, css_text)
        print("->>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>"+element.tag_name)
        for property in element.properties:
           print(str(property.name) + ": " + str(property.before_value) + " -> " + str(property.after_value)+ " -> " + str(property.calculated_value))
        print("->> "+css_text)
        for property_model in element.properties:
            property_model.has_color = _register_colors(property_model.before_value, color_scheme)

    context.set("dom_tree", root)
    context.set("color_scheme", color_scheme)

    print({
        "dom.capture_done": {
            "screenshot_path": screenshot_path,
            "observed_color_count": len(color_scheme.get_colors()),
        }
    })
    _dom_tree_ready(context.dom_tree)
    _color_scheme_ready(context.color_scheme)

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

        for property in element.properties:
            if property.type == "attribute":
                continue

            search_name = property.name.strip().lower()
            search_colors = _color_signature(property.before_value)
            property.is_defined = True
            property.type = "matched"
            if (
                matches_default_value(property.before_value, get_default_values(property.name))
                or str(property.before_value).strip().casefold() in {"none"}
            ):
                not_matched.append(property)
                continue

            if (search_name, search_colors) not in found_properties:
                if _should_keep_unmatched_property(element, property):
                    property.is_defined = False
                    property.type = "inherited"
                    continue
                else:
                    not_matched.append(property)

        for name in [property.name for property in not_matched]:
            element.remove_property(name) 

    elif css_text == "":
        for property in tuple(element.properties):
            if property.type == "attribute":
                continue

            if _should_keep_unmatched_property(element, property):
                property.is_defined = False
                property.type = "inherited"
                continue

            element.remove_property(property.name)

   
def _should_keep_unmatched_property(element: Element, property: Property) -> bool:
    if matches_default_value(property.before_value, get_default_values(property.name)) or property.before_value in ("none","None"):
        return False

    return (
        (property.name in ("font-weight", "font-size","color") and element.has_text)
        or (
            element.tag_name == "body"
            and property.name in ("color", "background-color")
        )
        or (property.name in ("fill", "stroke") and element.category == "decoration")
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
