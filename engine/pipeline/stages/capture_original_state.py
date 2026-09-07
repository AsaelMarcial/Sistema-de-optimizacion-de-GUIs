from __future__ import annotations

import re
from collections import Counter, deque
from itertools import batched
from pathlib import Path
from typing import Any

from flask import g

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.source_code_handler.local_asset_rewriter import (
    extract_reference_candidates,
)
from engine.domain.data.scope_css import CSSPROPERTIES, get_default_values
from engine.domain.data.scope_html_elements import get_html_element_category
from engine.domain.models.color_scheme import Color
from engine.domain.models.element import Element, Property, SVG_PAINT_TAGS
from engine.domain.utils.parsers import matches_default_value
from engine.pipeline.glow_runtime import (
    glow_flow,
    glow_task,
)
from engine.utilities.token_specification import classify_value
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
        classified_strings = tuple(classify_value(str(item)) for item in strings)

        layout_nodes = {
            int(backend_node_id): {
                "tag_name": tag_name,
                "styles": {
                    name: {
                        "value": str(strings[value_index]),
                        "tokens": classified_strings[value_index],
                    }
                    for name, value_index in zip(
                        whitelist_styles,
                        layout["styles"][layout_index],
                    )
                    if isinstance(value_index, int) and 0 <= value_index < len(strings)
                },
            }
            for layout_index, node_index in enumerate(layout.get("nodeIndex", ()))
            if (
                (backend_node_id := nodes["backendNodeId"][node_index])
                and (
                    tag_name := str(strings[nodes["nodeName"][node_index]])
                    .strip()
                    .lower()
                )
                != "#document"
            )
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
    page_builder: PageBuilder,
) -> tuple[dict[int, tuple[dict[str, Any], Element]], int, int, set[int], set[int]]:
    traversal_stack = deque(
        [(page_builder.get_full_document_node(refresh=True), False)]
    )
    approved: dict[int, tuple[dict[str, Any], Element]] = {}
    html_backend_node_id: int | None = None
    body_backend_node_id: int | None = None
    found_stylesheet_owner_backend_node_ids: set[int] = set()
    meta_element_backend_node_ids: set[int] = set()

    while traversal_stack:
        current_node, visited = traversal_stack.pop()
        children_nodes = (current_node.get("children") or []) + (
            current_node.get("pseudoElements") or []
        )
        attributes = current_node.get("attributes") or []

        if not visited:
            traversal_stack.append((current_node, True))
            traversal_stack.extend(
                (child_node, False) for child_node in reversed(children_nodes)
            )
            continue

        if is_approved(
            current_node, approved, stylesheet_owner_backend_node_ids, layout_nodes
        ):
            element = Element(
                backend_node_id=current_node.get("backendNodeId", 1),
                node_id=current_node.get("nodeId"),
                tag_name=str(current_node.get("nodeName") or "").strip().lower(),
                node_type=int(current_node.get("nodeType") or 0),
                category=get_html_element_category(
                    str(current_node.get("nodeName") or "").strip().lower()
                ),
                node_value=current_node.get("nodeValue"),
            )
            if element.tag_name in SVG_PAINT_TAGS:
                element.category = "decoration"

            if element.backend_node_id in layout_nodes:
                box_model = page_builder.get_box_model(element.backend_node_id)
                element.height = box_model.pop("height", None)
                element.width = box_model.pop("width", None)
                element.box_model = box_model
                for name, style_info in layout_nodes[element.backend_node_id][
                    "styles"
                ].items():
                    element.properties.append(
                        Property(
                            name=name,
                            before_value=style_info["value"],
                            value_tokens=style_info["tokens"],
                        )
                    )

            for name, value in list(batched(attributes, 2)):
                if str(name).strip().casefold() in _IMAGE_ATTRIBUTES or (
                    element.tag_name == "meta"
                    and str(name).strip().casefold() == "name"
                    and str(value).strip().casefold() == "color-scheme"
                ):
                    element.properties.append(
                        Property(
                            name=str(name).strip().casefold(),
                            before_value=str(value).strip(),
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
        stylesheet_owner_backend_node_ids - found_stylesheet_owner_backend_node_ids
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
            f"DOM tree build failed: missing_layout_tags={missing_layout_tags}"
        )

    html = approved[html_backend_node_id][1]

    for raw_node, element in approved.values():
        child_nodes = (raw_node.get("children") or []) + (
            raw_node.get("pseudoElements") or []
        )
        for child_node in child_nodes:
            child_backend_node_id = int(child_node.get("backendNodeId") or 0)
            child_entry = approved.get(child_backend_node_id)
            if child_entry is not None:
                element.add_child(child_entry[1])

    reachable_backend_node_ids = {
        element.backend_node_id for element in html.iter_dfs()
    }
    orphan_backend_node_ids = set(approved) - reachable_backend_node_ids

    if orphan_backend_node_ids:
        raise RuntimeError(
            f"DOM tree contiene elementos huerfanos: {sorted(orphan_backend_node_ids)}"
        )

    return {
        backend_node_id: element
        for backend_node_id, (_raw_node, element) in approved.items()
    }


@glow_flow
def capture_original_state() -> None:
    whitelist_styles = list(CSSPROPERTIES.keys())
    before_screenshot = g.project_context.GENERATED_FILES_REGISTRY[
        Path("before.png")
    ].absolute_path
    screenshot_path = g.page_builder.capture_fullpage_screenshot(
        output_path=before_screenshot
    )
    layout_nodes = process_dom_snapshot(
        g.page_builder.extract_raw_snapshot(whitelist_styles), whitelist_styles
    )
    stylesheet_owner_backend_node_ids = {
        stylesheet.owner_node
        for stylesheet in g.style.stylesheets.values()
        if isinstance(stylesheet.owner_node, int)
    }
    (
        approved,
        html_backend_node_id,
        body_backend_node_id,
        stylesheet_owner_backend_node_ids,
        meta_element_backend_node_ids,
    ) = approve_elements(
        stylesheet_owner_backend_node_ids, layout_nodes, g.page_builder
    )
    elements = build_element_tree(
        approved,
        layout_nodes,
        html_backend_node_id,
    )

    g.dom_tree.html = elements[html_backend_node_id]
    g.dom_tree.body = elements[body_backend_node_id]
    g.dom_tree.elements = elements
    g.dom_tree.stylesheet_owners = {
        backend_node_id: elements[backend_node_id]
        for backend_node_id in stylesheet_owner_backend_node_ids
        if backend_node_id in elements
    }
    g.dom_tree.meta_elements = {
        backend_node_id: elements[backend_node_id]
        for backend_node_id in meta_element_backend_node_ids
        if backend_node_id in elements
    }
    viewport_size = g.page_builder.viewport_size
    g.dom_tree.page_width = int(viewport_size.get("width") or 0)
    g.dom_tree.page_height = int(viewport_size.get("height") or 0)

    for element in g.dom_tree.iter_full_dfs():
        for property_model in element.properties:
            attribute_name = (
                property_model.name if property_model.type == "attribute" else None
            )
            for reference in extract_reference_candidates(
                property_model.before_value,
                attribute_name=attribute_name,
            ):
                project_file = g.project_context.project_file(reference)
                if project_file is None:
                    continue

                if project_file.file_type == "svg":
                    element.category = "decoration"

                if project_file.runtime_information is None:
                    continue

                property_model.resource = project_file.runtime_information
                project_file.add_usage(element.backend_node_id)
                break

        matched_properties: dict[str, list[Any]] = {}
        property_names = {
            property_model.name.strip().lower()
            for property_model in element.properties
            if property_model.type != "attribute"
        }

        if (
            property_names
            and element.node_id is not None
            and not element.tag_name.startswith("#")
            and not element.tag_name.startswith("::")
        ):
            matched_styles = g.page_builder.get_matched_styles(element.node_id)
            matched_properties = g.style.register_element_sources(
                element.backend_node_id,
                matched_styles,
                property_names,
            )

        _filter_properties(element, matched_properties)

        for property_model in element.properties:
            colors = _search_colors(property_model.before_value)
            if len(colors) >= 1:
                for color in colors:
                    g.color_scheme.add_color(color)
                property_model.has_color = True

    print(
        {
            "dom.capture_done": {
                "screenshot_path": screenshot_path,
                "observed_color_count": len(g.color_scheme.get_colors()),
                "element_count": len(g.dom_tree.elements),
                "page_width": g.dom_tree.page_width,
                "page_height": g.dom_tree.page_height,
            }
        }
    )


def _filter_properties(
    element: Element,
    matched_properties: dict[str, list[Any]],
) -> None:
    for property_model in tuple(element.properties):
        if property_model.type == "attribute":
            continue

        property_name = property_model.name.strip().lower()
        property_value = str(property_model.before_value or "").strip().casefold()
        is_default = matches_default_value(
            property_model.before_value,
            get_default_values(property_model.name),
        ) or property_value == "none"

        if is_default and property_model.resource is None:
            element.remove_property(property_model.name)
            continue

        if matched_properties.get(property_name):
            property_model.is_defined = True
            property_model.type = "matched"
            continue

        if _should_keep_unmatched_property(element, property_model):
            property_model.is_defined = False
            property_model.type = "inherited"
            continue

        element.remove_property(property_model.name)


def _should_keep_unmatched_property(element: Element, property: Property) -> bool:
    if matches_default_value(
        property.before_value, get_default_values(property.name)
    ) or property.before_value in ("none", "None"):
        return False

    return (
        bool(extract_reference_candidates(property.before_value))
        or property.resource is not None
        or (property.name in ("font-weight", "font-size", "color") and element.has_text)
        or (
            element.tag_name == "body"
            and property.name in ("color", "background-color")
        )
        or (property.name in ("fill", "stroke") and element.category == "decoration")
        or (
            property.name
            in (
                "background-image",
                "border-image-source",
                "mask-image",
                "list-style-image",
            )
            and element.category == "decoration"
        )
    )


def _search_colors(value: str | None) -> Counter[Color]:
    RE_COLOR_START = re.compile(
        r"(?i)(#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(|\b[a-z]{3,}\b)"
    )
    value = value or ""
    founded_colors: Counter[Color] = Counter()
    for match in RE_COLOR_START.finditer(value):
        start = match.start()
        mcolor = Color.match(value, start=start)
        if mcolor is not None:
            founded_colors[Color(mcolor.color)] += 1

    return Counter(founded_colors)
