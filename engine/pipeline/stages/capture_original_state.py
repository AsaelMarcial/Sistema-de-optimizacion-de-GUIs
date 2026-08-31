from __future__ import annotations

from collections import deque
from itertools import batched
from typing import Any

import tinycss2
from prefect.states import Completed, State

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.source_code_handler.local_asset_rewriter import (
    extract_reference_candidates,
)
from engine.domain.data.scope_css import CSSPROPERTIES, get_default_values
from engine.domain.data.scope_html_elements import get_html_element_category
from engine.domain.models.asset_records import AssetRecords, LocalAsset
from engine.domain.models.color_scheme import Color, ColorScheme
from engine.domain.models.element import DomTree, Element, Property
from engine.domain.models.session import Session
from engine.domain.utils.parsers import matches_default_value
from engine.pipeline.glow_runtime import (
    glow_flow,
    glow_task,
)
from engine.validators.specifics import is_approved

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
def process_dom_snapshot(
    snapshot: dict[str, Any],
    whitelist_styles: list[str],
) -> dict[int, dict[str, Any]]:
    try:
        strings = snapshot["strings"]
        document = snapshot["documents"][0]
        nodes = document["nodes"]
        layout = document["layout"]

        layout_nodes = {
            int(nodes["backendNodeId"][node_index]): {
                "tag_name": tag_name,
                "styles": {
                    name: str(strings[value])
                    for name, value in zip(
                        whitelist_styles,
                        layout["styles"][layout_index],
                    )
                    if value is not None
                },
            }
            for layout_index, node_index in enumerate(layout.get("nodeIndex", ()))
            if nodes["backendNodeId"][node_index]
            and (
                tag_name := str(strings[nodes["nodeName"][node_index]])
                .strip()
                .lower()
            ) != "#document"
        }
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"DOMSnapshot invalido: {exc}") from exc

    if not layout_nodes:
        raise RuntimeError("DOMSnapshot no devolvio nodos con layout.")

    return layout_nodes


@glow_task
def approve_elements(
    stylesheet_owner_backend_node_ids: set[int],
    layout_nodes: dict[int, dict[str, Any]],
    page_builder: PageBuilder
) -> tuple[dict[int, tuple[dict[str, Any], Element]], int, int, set[int], set[int]]:
    traversal_stack = deque([(page_builder.get_full_document_node(refresh=True), False)])
    approved: dict[int, tuple[dict[str, Any], Element]] = {}
    html_backend_node_id: int | None = None
    body_backend_node_id: int | None = None
    found_stylesheet_owner_backend_node_ids: set[int] = set()
    meta_element_backend_node_ids: set[int] = set()

    while traversal_stack:
        current_node, visited = traversal_stack.pop()
        children_nodes = (
            (current_node.get("children") or [])
            + (current_node.get("pseudoElements") or [])
        )
        attributes = current_node.get("attributes") or []

        if not visited:
            traversal_stack.append((current_node, True))
            traversal_stack.extend(
                (child_node, False)
                for child_node in reversed(children_nodes)
            )
            continue

        if (is_approved(current_node, approved, stylesheet_owner_backend_node_ids, layout_nodes)):
            element = Element(
                backend_node_id=int(current_node.get("backendNodeId")),
                node_id=current_node.get("nodeId"),
                tag_name=str(current_node.get("nodeName") or "").strip().lower(),
                node_type=int(current_node.get("nodeType") or 0),
                category=get_html_element_category(str(current_node.get("nodeName") or "").strip().lower()),
                node_value=current_node.get("nodeValue"),
            )
            if element.backend_node_id in layout_nodes:
                box_model = page_builder.get_box_model(element.backend_node_id)
                element.height = box_model.pop("height", None)
                element.width = box_model.pop("width", None)
                element.box_model = box_model
                for name, value in layout_nodes[element.backend_node_id]["styles"].items():
                    element.properties.append(
                        Property(
                            name=name,
                            before_value=value,
                        )
                    )

            for name, value in list(batched(attributes, 2)):
                if str(name).strip().casefold() in _IMAGE_ATTRIBUTES or (element.tag_name == "meta" and str(name).strip().casefold() == "name" and str(value).strip().casefold() == "color-scheme"):
                    element.properties.append(
                        Property(
                            name=str(name).strip().casefold(),
                            before_value=str(value).strip().casefold(),
                            type="attribute",
                            is_defined=True,
                        )
                    )

            approved[element.backend_node_id] = (current_node, element)

            match element.tag_name:
                case "html":
                    html_backend_node_id = element.backend_node_id
                case "body":
                    body_backend_node_id = element.backend_node_id
                case "meta":
                    meta_element_backend_node_ids.add(element.backend_node_id)

            if element.backend_node_id in stylesheet_owner_backend_node_ids:
                found_stylesheet_owner_backend_node_ids.add(element.backend_node_id)

    missing_stylesheet_owner_backend_node_ids = (
        stylesheet_owner_backend_node_ids
        - found_stylesheet_owner_backend_node_ids
    )

    if (
        not approved
        or html_backend_node_id is None
        or body_backend_node_id is None
        or bool(missing_stylesheet_owner_backend_node_ids)
    ):
        raise RuntimeError(
            "DOM tree approval failed: "
            f"approved={len(approved)}, "
            f"html={html_backend_node_id}, "
            f"body={body_backend_node_id}, "
            "missing_stylesheet_owners="
            f"{sorted(missing_stylesheet_owner_backend_node_ids)}"
        )

    return (
        dict(sorted(approved.items())),
        html_backend_node_id,
        body_backend_node_id,
        found_stylesheet_owner_backend_node_ids,
        meta_element_backend_node_ids,
    )


@glow_task
def build_element_tree(
    approved: dict[int, tuple[dict[str, Any], Element]],
    layout_nodes: dict[int, dict[str, Any]],
    html_backend_node_id: int,
) -> dict[int, Element]:
    missing_layout_backend_node_ids = set(layout_nodes) - set(approved)
    if missing_layout_backend_node_ids:
        missing_layout_tags = sorted(
            layout_nodes[backend_node_id].get("tag_name", "unknown")
            for backend_node_id in missing_layout_backend_node_ids
        )
        raise RuntimeError(
            "DOM tree build failed: missing_layout_tags="
            f"{missing_layout_tags}"
        )

    html = approved[html_backend_node_id][1]

    for raw_node, element in approved.values():
        child_nodes = (
            (raw_node.get("children") or [])
            + (raw_node.get("pseudoElements") or [])
        )
        for child_node in child_nodes:
            child_backend_node_id = int(child_node.get("backendNodeId") or 0)
            child_entry = approved.get(child_backend_node_id)
            if child_entry is not None:
                element.add_child(child_entry[1])

    reachable_backend_node_ids = {
        element.backend_node_id
        for element in html.iter_dfs()
    }
    orphan_backend_node_ids = set(approved) - reachable_backend_node_ids

    if orphan_backend_node_ids:
        raise RuntimeError(
            "DOM tree contiene elementos huerfanos: "
            f"{sorted(orphan_backend_node_ids)}"
        )

    return {
        backend_node_id: element
        for backend_node_id, (_raw_node, element) in approved.items()
    }

@glow_task
def _color_scheme_ready(color_scheme: ColorScheme | None) -> State:
    if color_scheme is None or len(color_scheme.get_colors()) == 0:
        raise RuntimeError("No se genero ColorScheme.")
    else:
        return Completed(message="ColorScheme esta listo.")

@glow_flow
def capture_original_state(
    session: Session,
    page_builder: PageBuilder,
    color_scheme: ColorScheme,
    asset_records: AssetRecords,
    dom_tree: DomTree,
) -> None:

    whitelist_styles = list(CSSPROPERTIES.keys())
    before_screenshot = session.get_path("before.png", "artifacts", "png")
    screenshot_path = page_builder.capture_fullpage_screenshot(output_path=before_screenshot)
    layout_nodes = process_dom_snapshot(page_builder.extract_raw_snapshot(whitelist_styles), whitelist_styles)
    stylesheet_owner_backend_node_ids = {
        stylesheet.owner_node
        for stylesheet in page_builder.styles.stylesheets.values()
        if isinstance(stylesheet.owner_node, int)
    }
    (
        approved,
        html_backend_node_id,
        body_backend_node_id,
        stylesheet_owner_backend_node_ids,
        meta_element_backend_node_ids,
    ) = approve_elements(
        stylesheet_owner_backend_node_ids,
        layout_nodes,
        page_builder
    )
    elements = build_element_tree(
        approved,
        layout_nodes,
        html_backend_node_id,
    )

    dom_tree.html = elements[html_backend_node_id]
    dom_tree.body = elements[body_backend_node_id]
    dom_tree.elements = elements
    dom_tree.stylesheet_owners = {
        backend_node_id: elements[backend_node_id]
        for backend_node_id in stylesheet_owner_backend_node_ids
        if backend_node_id in elements
    }
    dom_tree.meta_elements = {
        backend_node_id: elements[backend_node_id]
        for backend_node_id in meta_element_backend_node_ids
        if backend_node_id in elements
    }
    viewport_size = page_builder.viewport_size
    dom_tree.page_width = int(viewport_size.get("width") or 0)
    dom_tree.page_height = int(viewport_size.get("height") or 0)

    svg_paths = tuple(session.get_by_type(".svg"))
    for element in dom_tree.iter_full_dfs():
        _resolve_image_sources(
            element,
            session,
            asset_records,
            svg_paths,
        )
        _filter_properties(
            element,
            _matched_css_text(page_builder, element),
        )

        for property_model in element.properties:
            colors = _search_colors(property_model.before_value)
            if len(colors) >= 1:
                for color in colors:
                    color_scheme.add_color(color)
                property_model.has_color = True

    print({
        "dom.capture_done": {
            "screenshot_path": screenshot_path,
            "observed_color_count": len(color_scheme.get_colors()),
            "element_count": len(dom_tree.elements),
            "page_width": dom_tree.page_width,
            "page_height": dom_tree.page_height,
        }
    })

    _color_scheme_ready(color_scheme)

def _resolve_image_sources(
    element: Element,
    session: Session,
    asset_records: AssetRecords,
    svg_paths: tuple[Any, ...],
) -> None:
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
            asset = asset_records.find_asset(candidate)
            if asset is None:
                asset = asset_records.add_asset(
                    source=candidate,
                    origin="unknown",
                )

            asset.add_usage(element.backend_node_id)
            if image_reference.image_source is None:
                image_reference.image_source = asset

            if (
                isinstance(asset, LocalAsset)
                and asset.origin in {"local", "generated"}
                and asset.load_status
                and any(
                    svg_path.stem.lower() == asset.path.stem.lower()
                    for svg_path in svg_paths
                )
            ):
                image_reference.image_source = asset
                element.category = "decoration"
                break


def _matched_css_text(
    page_builder: PageBuilder,
    element: Element,
) -> str:
    if (
        element.node_id is None
        or element.tag_name.startswith("#")
        or element.tag_name.startswith("::")
    ):
        return ""

    css_text = ""
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
                    css_text += "\n" + str(property.get("name")) + ": " + str(property.get("value"))
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
    return css_text


def _filter_properties(element: Element, css_text: str) -> None:
    if css_text != "" and not element.tag_name.startswith("#") and not element.tag_name.startswith("::"):
        raw_nodes = tinycss2.parse_declaration_list(css_text, skip_comments=True)
        found_properties: set[tuple[str, tuple[str, ...]]] = set()
        
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

def _color_signature(value: str | None) -> tuple[str, ...]:
    return tuple(
        sorted(
            color
            .convert("srgb")
            .to_string(
                comma=True,
                alpha=True,
                rounding="decimal",
                precision=0,
            )
            for color in _search_colors(value or "")
        )
    )

def _search_colors(value: str | None) -> set(Color):
    value = value or ""
    founded_colors: set[Color] = set()
    start = 0
    while start < len(value):
        match = Color.match(value, start=start)
        if match is None:
            start += 1
            continue

        if match.color.alpha(nans=False) > 0:
            founded_colors.add(match.color)

        end = int(getattr(match, "end", start + 1))
        start = max(end, start + 1)
    return founded_colors
