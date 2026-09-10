from __future__ import annotations

import re
from collections import Counter
from itertools import batched
from pathlib import Path
from typing import Any

from flask import g

from engine.adapters.source_code_handler.local_asset_rewriter import (
    extract_reference_candidates,
)
from engine.domain.data.scope_css import CSSPROPERTIES, get_default_values
from engine.domain.data.scope_html_elements import get_html_element_category
from engine.domain.models.color_scheme import Color
from engine.domain.models.element import Element, Property
from engine.domain.utils.parsers import matches_default_value
from engine.pipeline.glow_runtime import glow_flow, glow_task
from engine.utilities.token_specification import classify_value

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
_ALLOWED_ATTRIBUTES = {
    "data-theme",
    "fill",
    "stroke",
}
_COLOR_START_RE = re.compile(
    r"(?i)(#[0-9a-f]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(|\b[a-z]{3,}\b)"
)


@glow_task
def process_dom_snapshot():
    whitelist = list(CSSPROPERTIES)
    snapshot = g.page_builder.extract_raw_snapshot(whitelist)
    strings_pool = snapshot["strings"]
    document = snapshot["documents"][0]
    nodes = document["nodes"]
    layout = document["layout"]
    ignored_tags = {"#document", "script", "noscript", "title"}

    if not (layout_indices := layout.get("nodeIndex")):
        raise RuntimeError("DOMSnapshot no devolvio nodos con layout.")

    layout_by_node = {
        node_idx: layout_idx for layout_idx, node_idx in enumerate(layout_indices)
    }
    required = set(layout_by_node)
    pending = list(required)

    while pending:
        parent = nodes["parentIndex"][pending.pop()]
        if isinstance(parent, int) and parent >= 0 and parent not in required:
            required.add(parent)
            pending.append(parent)

    stylesheet_owner_node_ids = {
        stylesheet.owner_node
        for stylesheet in g.style.stylesheets.values()
        if isinstance(stylesheet.owner_node, int)
    }
    classified_strings_cache = {
        value_index: classify_value(str(strings_pool[value_index]))
        for layout_idx in layout_by_node.values()
        for value_index in layout["styles"][layout_idx]
        if isinstance(value_index, int) and value_index >= 0
    }

    layout_nodes = (
        Element(
            backend_node_id=(backend_id := int(nodes["backendNodeId"][idx] or 0)),
            node_id=None,
            tag_name=(tag := str(strings_pool[nodes["nodeName"][idx]]).lower()),
            category=get_html_element_category(tag),
            node_type=int(nodes["nodeType"][idx]),
            node_value=str(strings_pool[value_idx])
            if tag == "#text" and (value_idx := nodes["nodeValue"][idx]) >= 0
            else None,
            width=(
                box := g.page_builder.get_box_model(backend_id)
                if (layout_idx := layout_by_node.get(idx)) is not None
                else {}
            ).pop("width", None),
            height=box.pop("height", None),
            box_model=box or None,
            attributes=[
                Property(
                    name=name,
                    before_value=str(strings_pool[value_idx]),
                    type="attribute",
                    is_defined=True,
                )
                for name_idx, value_idx in batched(nodes["attributes"][idx], 2)
                if (name := str(strings_pool[name_idx]).casefold())
                in _ALLOWED_ATTRIBUTES
                or (
                    tag == "meta"
                    and name == "name"
                    and str(strings_pool[value_idx]).casefold() == "color-scheme"
                )
            ],
            image_references=[
                Property(
                    name=name,
                    before_value=str(strings_pool[value_idx]),
                    type="attribute",
                    is_defined=True,
                )
                for name_idx, value_idx in batched(nodes["attributes"][idx], 2)
                if (name := str(strings_pool[name_idx]).casefold()) in _IMAGE_ATTRIBUTES
            ],
            properties=[
                Property(
                    name=whitelist[index],
                    before_value=str(strings_pool[value_idx]),
                    value_tokens=classified_strings_cache[value_idx],
                )
                for index, value_idx in enumerate(
                    layout["styles"][layout_idx] if layout_idx is not None else ()
                )
                if isinstance(value_idx, int) and value_idx >= 0
            ],
        )
        for idx in required
        if (nodes["backendNodeId"][idx] or 0)
        and str(strings_pool[nodes["nodeName"][idx]]).lower() not in ignored_tags
    )

    for element in layout_nodes:
        g.dom_tree.elements[element.backend_node_id] = element
        if element.tag_name == "html":
            g.dom_tree.html = element
        elif element.tag_name == "body":
            g.dom_tree.body = element
        elif element.tag_name == "meta":
            g.dom_tree.meta_elements[element.backend_node_id] = element

    pending = [(g.page_builder.document_root, None)]
    while pending:
        node, parent = pending.pop()
        element = g.dom_tree.elements.get(int(node.get("backendNodeId") or 0))

        if element is not None:
            if isinstance(node_id := node.get("nodeId"), int):
                element.node_id = node_id
                if node_id in stylesheet_owner_node_ids:
                    g.dom_tree.stylesheet_owners[element.backend_node_id] = element
            if parent is not None:
                parent.add_child(element)

        pending.extend(
            (child, element or parent)
            for child in reversed(
                (node.get("children") or []) + (node.get("pseudoElements") or [])
            )
        )

    missing_layout = [
        int(nodes["backendNodeId"][idx] or 0)
        for idx in layout_by_node
        if int(nodes["backendNodeId"][idx] or 0) not in g.dom_tree.elements
        and str(strings_pool[nodes["nodeName"][idx]]).lower() not in ignored_tags
    ]
    missing_parents = [
        int(nodes["backendNodeId"][parent_idx] or 0)
        for idx in required
        if isinstance(parent_idx := nodes["parentIndex"][idx], int)
        and parent_idx >= 0
        and int(nodes["backendNodeId"][idx] or 0) in g.dom_tree.elements
        and int(nodes["backendNodeId"][parent_idx] or 0) not in g.dom_tree.elements
        and str(strings_pool[nodes["nodeName"][parent_idx]]).lower() not in ignored_tags
    ]

    if (
        g.dom_tree.html is None
        or g.dom_tree.body is None
        or missing_layout
        or missing_parents
    ):
        raise RuntimeError(
            "DOM tree build failed validation: "
            f"html={bool(g.dom_tree.html)}, "
            f"body={bool(g.dom_tree.body)}, "
            f"missing_layout={missing_layout[:10]}, "
            f"missing_parents={missing_parents[:10]}"
        )

    viewport_size = g.page_builder.viewport_size
    g.dom_tree.page_width = int(viewport_size.get("width") or 0)
    g.dom_tree.page_height = int(viewport_size.get("height") or 0)


@glow_flow
def capture_original_state() -> None:
    before_screenshot = g.project_context.GENERATED_FILES_REGISTRY[
        Path("before.png")
    ].absolute_path
    screenshot_path = g.page_builder.capture_fullpage_screenshot(
        output_path=before_screenshot
    )

    process_dom_snapshot()

    for element in g.dom_tree.iter_full_dfs():
        _process_properties(element)

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


def _process_properties(element: Element) -> None:
    property_names = {
        property_model.name.strip().lower()
        for property_model in element.properties
        if property_model.type != "attribute"
    }

    matched_properties = g.style.sources_by_node.get(element.backend_node_id)
    if (
        matched_properties is None
        and property_names
        and element.node_id is not None
        and not element.tag_name.startswith("#")
    ):
        matched_properties = g.style.register_element_sources(
            element.backend_node_id,
            g.page_builder.get_matched_styles(element.node_id),
            property_names,
            include_user_agent=element.tag_name == "input",
        )

    matched_properties = matched_properties or {}

    for property_model in (*element.image_references, *tuple(element.properties)):
        _bind_resource(element, property_model, matched_properties)

    _filter_properties(element, matched_properties)

    for property_model in (
        *element.properties,
        *element.attributes,
        *element.image_references,
    ):
        colors = _search_colors(property_model.before_value)
        if not colors:
            continue

        for color in colors:
            g.color_scheme.add_color(color)
        property_model.has_color = True


def _bind_resource(
    element: Element,
    property_model: Property,
    matched_properties: dict[str, list[Any]],
) -> None:
    property_name = property_model.name.strip().lower()
    reference_sources = (
        [(property_model.before_value, property_model.name, g.project_context.html)]
        if property_model.type == "attribute"
        else [
            (
                getattr(source, "value", None),
                None,
                stylesheet.project_file
                if (
                    stylesheet := g.style.stylesheets.get(
                        getattr(source, "stylesheet_id", None) or ""
                    )
                )
                and stylesheet.project_file is not None
                else g.project_context.html,
            )
            for source in matched_properties.get(property_name, ())
        ]
        or [(property_model.before_value, None, g.project_context.html)]
    )

    for value, attribute_name, source_file in reference_sources:
        references = extract_reference_candidates(value, attribute_name)
        if references and property_model not in element.image_references:
            property_model.is_defined = True
            element.image_references.append(property_model)
            if property_model in element.properties:
                element.properties.remove(property_model)

        for reference in references:
            project_file = g.project_context.project_file(reference, source_file)
            if project_file is None:
                continue

            if project_file.file_type == "svg":
                element.category = "decoration"

            if project_file.runtime_information is not None:
                property_model.resource = project_file.runtime_information
                project_file.add_usage(element.backend_node_id)
                return


def _filter_properties(
    element: Element,
    matched_properties: dict[str, list[Any]],
) -> None:
    computed_by_name = {
        property_model.name.strip().lower(): property_model
        for property_model in element.properties
        if property_model.type != "attribute"
    }

    for property_model in tuple(element.attributes):
        property_name = property_model.name.strip().lower()
        computed_property = computed_by_name.get(property_name)

        if (
            element.tag_name == "html"
            and property_name == "data-theme"
            and bool(str(property_model.before_value or "").strip())
        ) or (
            computed_property is not None
            and _same_css_value(
                property_model.before_value,
                computed_property.before_value,
            )
        ):
            property_model.is_defined = True
        else:
            element.attributes.remove(property_model)

    for property_model in tuple(element.properties):
        property_name = property_model.name.strip().lower()
        computed_property = computed_by_name.get(property_name)

        computed_value = (
            computed_property.before_value
            if computed_property is not None
            else property_model.before_value
        )
        property_value = str(computed_value or "").strip().casefold()
        sources = matched_properties.get(property_name, ())
        is_default = matches_default_value(
            computed_value,
            get_default_values(property_name),
        ) or property_value in {"", "none"}
        is_visual_baseline = (element.has_text and property_name == "color") or (
            element.tag_name == "body"
            and property_name in {"color", "background-color"}
            and not is_default
        )

        if is_default and not is_visual_baseline:
            element.remove_property(property_name)
            continue

        if regular_source := next(
            (
                source
                for source in sources
                if getattr(source, "origin", None) == "regular"
                and getattr(source, "target_property", property_name) == property_name
                and _same_css_value(getattr(source, "value", None), computed_value)
            ),
            None,
        ):
            property_model.type = (
                "inline"
                if regular_source.source_type in {"inline", "attribute"}
                else "matched"
            )
            property_model.is_defined = True
            continue

        is_input_override = (
            element.tag_name == "input"
            and not is_default
            and any(
                getattr(source, "origin", None) == "user-agent" for source in sources
            )
            and not any(
                _same_css_value(getattr(source, "value", None), computed_value)
                for source in sources
                if getattr(source, "origin", None) == "user-agent"
            )
        )

        if is_visual_baseline or is_input_override:
            property_model.type = "inherited"
            property_model.is_defined = False
            continue

        element.remove_property(property_name)


def _same_css_value(declared: str | None, computed: str | None) -> bool:
    declared_value = str(declared or "").strip()
    computed_value = str(computed or "").strip()

    declared_colors = _search_colors(declared_value)
    if declared_colors:
        computed_colors = _search_colors(computed_value)
        return bool(computed_colors) and declared_colors <= computed_colors

    return (
        declared_value.casefold() == computed_value.casefold()
        or "var(" in declared_value.casefold()
    )


def _search_colors(value: str | None) -> Counter[Color]:
    value = value or ""
    founded_colors: Counter[Color] = Counter()
    for match in _COLOR_START_RE.finditer(value):
        start = match.start()
        mcolor = Color.match(value, start=start)
        if mcolor is not None:
            founded_colors[Color(mcolor.color)] += 1

    return Counter(founded_colors)
