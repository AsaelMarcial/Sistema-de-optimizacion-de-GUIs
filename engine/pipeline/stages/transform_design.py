from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.source_code_handler.source_code_formatter import (
    export_runtime_sources,
)
from engine.domain.data.scope_css import CSSPROPERTIES, get_role, is_valid_name
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import (
    Color,
    ColorScheme,
    NEUTRAL_TONAL_STEPS,
    Tone,
)
from engine.domain.models.element import Attribute, Element, Property
from engine.domain.models.session import Session
from engine.domain.models.token import TokenInventory
from engine.domain.utils.css_generator import generate_theme_css
from engine.domain.utils.parsers import (
    extract_url_value,
    get_colors,
    has_gradient,
    is_svg_url,
    has_url_image,
    replace_property_values,
    is_css_value_contained,
)
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
import re
import io

SVG_PAINT_TAGS = ("svg", "circle", "rect", "ellipse", "line", "polyline", "polygon", "path")
SVG_DEFAULT_FILL_TAGS = ("path", "circle", "rect", "ellipse", "polygon", "polyline", "text", "use")

def _transformed_dom_tree_ready(root: Element) -> bool:
    try:
            #aqui iría una validación de que set_color_scheme sea true, set_theme link sea true, glow.css exista y set_data_theme true

        return False
    except Exception as exc:
        exception_type = type(exc).__name__
        
        raise RuntimeError(
            f"Operation failed due to an unexpected error [{exception_type}]: {exc}"
        ) from exc

def _color_scheme_ready(page_builder: PageBuilder) -> bool:
    return page_builder.set_color_scheme()

CONTRACT = StageContract(
    name="transform_design",
    requires=(
        context_value(K.SESSION, Session),
        context_value(K.PAGE_BUILDER, PageBuilder),
        context_value(K.DOM_TREE, Element),
        context_value(K.COLOR_SCHEME, ColorScheme),
        context_value(K.TOKEN_INVENTORY, TokenInventory),
    ),
    produces=(
        context_value(K.PAGE_BUILDER, PageBuilder, validator=_color_scheme_ready),
        context_value(K.DOM_TREE, Element),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    session = context.get(K.SESSION)
    page_builder = context.get(K.PAGE_BUILDER)
    root = context.get(K.DOM_TREE)
    color_scheme = context.get(K.COLOR_SCHEME)
    token_inventory = context.get(K.TOKEN_INVENTORY)

    context.trace.add_stage_event(CONTRACT.name, "start")

    page_builder.set_color_scheme()
    theme_link_ready = page_builder.set_theme_link()
    processed_svg_files: dict[Path, Path] = {}

    original_backgrounds = _original_backgrounds(root, page_builder)

    for element in root.iter_dfs():
        if not element.node_id or element.tag_name.startswith("#") or element.tag_name.startswith("::"):
            continue
        
        _update_properties(page_builder, element)

        _, original_ancestor_background_colors, original_inner_background_colors, original_background_data = next(
            (item for item in original_backgrounds if item[0] == element.backend_node_id), 
            (0, None, None, {}) 
        )

        for css_property in tuple(element.properties):
            actual_value = css_property.current_value
            before_colors = get_colors(css_property.before_value)

            match element.category, get_role(css_property.name):
                case "main-surface", "background":
                    if css_property.name == "background-image" or element.has_image:
                        _transform_property(
                            page_builder,
                            element,
                            css_property,
                            "unset"
                        )
                    
                    if not is_css_value_contained("rgb(0, 0, 0)", actual_value) and not is_css_value_contained("rgba(0, 0, 0, 1)", actual_value):
                        _transform_property(
                            page_builder,
                            element,
                            css_property,
                            "var(--Neutral-0)"
                        )

                case "container", "background":
                    if element.has_image:
                        continue
                    if has_gradient(css_property.current_value) or before_colors is None or len(before_colors) > 1:
                        _transform_property(
                            page_builder,
                            element,
                            css_property,
                            "unset"
                        )
                        continue

                    neutral_palette = color_scheme.get_palette("Neutral")
                    color = before_colors[0][1].convert("hct")

                    if element.tag_name in ("footer","header"):
                        _transform_property(
                            page_builder,
                            element,
                            css_property,
                            "unset"
                        )
                        continue

                    palette, tone, _steps = color_scheme.find_closest(color, "palettes")
                        
                    if color["t"] <= 40 and palette.name == "Neutral":
                        continue

                    target_tone = None

                    if element.tag_name == "nav":
                        if color["t"] > 40:
                            actual_ancestor_background_colors, _ = _actual_backgrounds(root, element)
                            target_tones = _differences(css_property.name, [("", color)], original_ancestor_background_colors, None, actual_ancestor_background_colors, None, element.tag_name, color_scheme, None, 30)
                            target_tone = target_tones[0] if target_tones else None
                    else:
                        surface_depth = max(element.depth or 1, 1)
                        for surface_ancestor in root.ancestors_of(element):
                            if surface_ancestor.tag_name == "body":
                                break
                            
                            surface_ancestor_background = surface_ancestor.effective_background
                            surface_ancestor_background_colors = get_colors(
                                surface_ancestor_background["before_value"]
                            )
                            if surface_ancestor_background["name"] and any(
                                color.alpha(nans=False) >= 0.1
                                for _value, color in surface_ancestor_background_colors or ()
                            ):
                                break

                            surface_depth -= 1

                        elevation_tones = tuple(
                            tone
                            for tone in (NEUTRAL_TONAL_STEPS)
                            if 10 <= int(tone) <= 50
                        )

                        best_tone = elevation_tones[
                            min(
                                max(surface_depth, 1) - 1,
                                len(elevation_tones) - 1,
                            )
                        ]

                        target_tone = neutral_palette.tone(best_tone)

                    if target_tone is not None:
                        _transform_property(
                                page_builder,
                                element,
                                css_property,
                                target_tone.to_var if isinstance(target_tone, Tone) else target_tone
                            )

                case "input", "foreground" | "background":
                    matched_rules = page_builder.get_matched_styles(element.node_id).get("matchedCSSRules")
                    for rulematch in matched_rules:
                        rule = rulematch.get("rule") or {}
                        if rule.get("origin") == "user-agent":
                            for property in rule.get("style").get("cssProperties"):
                                if property.get("name") == css_property.name and property:
                                    _transform_property(
                                        page_builder,
                                        element,
                                        css_property,
                                        property.get("value")
                                    )
                    continue

                case "composed" | "typography", "background":
                    if element.has_image:
                        continue

                    actual_ancestor_background_colors, _ = _actual_backgrounds(root, element)

                    target_tones = _differences(css_property.name, before_colors, original_ancestor_background_colors, None, actual_ancestor_background_colors, None, element.tag_name, color_scheme, None, None)

                    if target_tones:
                        for tone in target_tones:
                            if isinstance(tone, Tone):
                                tone.color["t"] = tone.color["t"] - 10
                        token_value = replace_property_values(
                            css_property.before_value,
                            [value for value, _color in before_colors],
                            [
                                tone.to_var if isinstance(tone, Tone) else tone
                                for tone in target_tones
                            ],
                        )

                        _transform_property(
                            page_builder,
                            element,
                            css_property,
                            token_value
                        )

                case "main-surface" | "container" | "composed" | "typography" | "media" , "foreground":
                    if before_colors is None:
                        continue

                    actual_ancestor_background_colors, actual_inner_background_colors = _actual_backgrounds(root, element)
                    if element.category == "main-surface" and css_property.name == "color" and not is_css_value_contained("rgb(255, 255, 255)", css_property.before_value) and not is_css_value_contained("rgba(255, 255, 255, 1)", css_property.before_value):
                        _transform_property(
                            page_builder,
                            element,
                            css_property,
                            "var(--Neutral-100)"
                        )
                        continue

                    if (
                        css_property.name in ("text-shadow", "box-shadow")
                        and _should_clean_shadow(before_colors)
                    ):
                        _transform_property(
                            page_builder,
                            element,
                            css_property,
                            "unset"
                        )
                        continue

                    if css_property.name == "color":
                        continue

                    target_token_values = []

                    for value, color in before_colors:
                        if color.get("alpha") == 0  or is_css_value_contained("transparent", value):
                            target_token_values.append(value)
                            continue
                        elif color.convert("hct").get("t") >= 60:
                            palette, tone, _steps = color_scheme.find_closest(color, "palettes") or (None, None, None)
                            if palette is None or tone is None:
                                target_token_values.append(_serialize_color(color))
                                continue

                            target_token_values.append(tone.to_var)
                        else:
                            target_tones = _differences(css_property.name, [("", color)], original_ancestor_background_colors, original_inner_background_colors, actual_ancestor_background_colors, actual_inner_background_colors, element.tag_name, color_scheme, 60, None)
                            if target_tones:
                                target_token_values.append(
                                    target_tones[0].to_var
                                    if isinstance(target_tones[0], Tone)
                                    else target_tones[0]
                                )
                            else:
                                target_token_values.append(_serialize_color(color))

                    token_value = replace_property_values(
                        css_property.before_value,
                        [value for value, _color in before_colors],
                        target_token_values,
                    )

                    _transform_property(
                        page_builder,
                        element,
                        css_property,
                        token_value
                    )

                case "decoration", "foreground" | "background":
                    if before_colors is None:
                        continue

                    if element.tag_name in SVG_PAINT_TAGS:
                        actual_ancestor_background_colors, actual_inner_background_colors = _actual_backgrounds(root, element)
                        target_values = _differences(
                            css_property.name,
                            get_colors(actual_value),
                            original_ancestor_background_colors,
                            None,
                            actual_ancestor_background_colors,
                            None,
                            element.tag_name,
                            color_scheme,
                            None,
                            None
                        )
                        if target_values:
                            token_value = replace_property_values(
                                css_property.before_value,
                                [value for value, _color in before_colors],
                                [
                                    tone.to_var if isinstance(tone, Tone) else tone
                                    for tone in target_values
                                ],
                            )
                            _transform_property(
                                page_builder,
                                element,
                                css_property,
                                token_value
                            )

                case _,_:
                    continue
        if (element.category == "decoration" and element.tag_name not in SVG_PAINT_TAGS):
            actual_ancestor_background_colors, _ = _actual_backgrounds(root, element)
            _process_external_svg_decoration(
                session,
                page_builder,
                element,
                original_ancestor_background_colors,
                actual_ancestor_background_colors,
                color_scheme,
                processed_svg_files,
            )
            continue

        if element.has_text and not element.has_tag("body"):
            print(str(element.tag_name))
            actual_background_data = page_builder.get_background_colors(
                element.node_id
            ) or {}

            color_property = element.property("color")
            print("propiedad" + str(color_property))
            size_property = element.property("font-size")
            weight_property = element.property("font-weight")
            if color_property["name"] and actual_background_data:
                original_contrast_data = element.get_text_contrast(
                    color_property["before_value"],
                    original_background_data.get("background_colors"),
                    original_background_data.get("font-size") or size_property["before_value"],
                    original_background_data.get("font_weight") or weight_property["before_value"],
                ) if original_background_data is not None else None
                actual_contrast_data = element.get_text_contrast(
                    color_property["current_value"],
                    actual_background_data.get("background_colors"),
                    actual_background_data.get("font-size") or size_property["before_value"],
                    actual_background_data.get("font_weight") or weight_property["before_value"],
                ) if actual_background_data is not None else None
                print("original_background_data " +str(original_background_data))
                print("actual_background_data " +str(actual_contrast_data))
                print("font " +str(size_property) +str(weight_property))

                if actual_contrast_data is not None and not (color_property["has_changed"] and actual_contrast_data[2] >= actual_contrast_data[3]):
                    target_tone = _text_contrast_target_tone(
                        color_scheme,
                        Color(color_property["current_value"]),
                        actual_contrast_data,
                        actual_background_data,
                        original_contrast_data,
                        original_background_data,
                    )
                    print("target_tone " + str(target_tone))
                    if target_tone is not None:
                        property_model = next(
                            (
                                property_model
                                for property_model in element.properties
                                if property_model.name == color_property["name"]
                            ),
                            None,
                        )
                        if property_model is None:
                            continue

                        _transform_property(
                            page_builder,
                            element,
                            property_model,
                            target_tone.to_var
                        )
        _update_properties(page_builder, element)
        print("->>>>>"+element.tag_name)
        for property in element.properties:
            print(str(property.name) + ": " + str(property.before_value) + " -> " + str(property.after_value)+ " -> " + str(property.token_value))

    css_path = session.find_by_suffix("before", "html")[0].parent / "glow.css"
    token_inventory.generate_property_tokens(root)
    root_css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    theme_css = root_css.rstrip() + "\n\n" + generate_theme_css(token_inventory.property_tokens)
    css_path.write_text(theme_css, encoding="utf-8")
    session.save_in_before(css_path)
    data_theme_ready = page_builder.set_data_theme()
    theme_link_ready = page_builder.set_theme_link()
    page_builder.set_theme_stylesheet_text(theme_css)
    print(str(theme_link_ready))

    elements_by_node_id = {
        element.node_id: element
        for element in root.iter_dfs()
        if element.node_id is not None
    }
    for token in token_inventory.property_tokens.values():
        for element_id, property_name in token.element_ids:
            token_element = elements_by_node_id.get(element_id)
            if token_element is None:
                continue

            page_builder.set_effective_value(
                token_element.backend_node_id,
                token_element.node_id,
                property_name,
                token.to_var,
                token_element.tag_name,
            )

    page_builder.wait_for_style_ready()

    after_screenshot = session.get_path(
        "after.png",
        "artifacts",
        "png",
    )
    after_screenshot_path = page_builder.capture_fullpage_screenshot(
        output_path=after_screenshot
    )
    copied_after_paths = session.copy_area_files("before", "after")
    after_theme_css_path = session.parallel_path(css_path, "before", "after")
    source_export = _export_runtime_sources(session, page_builder)
    after_html_path = source_export.html_path
    after_css_paths = list(source_export.stylesheet_paths.values())

    context.set(K.DOM_TREE, root)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "after_screenshot_path": after_screenshot_path,
            "after_html_path": str(after_html_path),
            "after_theme_css_path": str(after_theme_css_path),
            "after_css_paths": [str(path) for path in after_css_paths],
            "copied_after_paths": [str(path) for path in copied_after_paths],
            "data_theme_ready": data_theme_ready,
            "theme_link_ready": theme_link_ready,
        },
    )
    return context


def _export_runtime_sources(
    session: Session,
    page_builder: PageBuilder,
) -> Any:
    before_html = session.find_by_suffix("before", "html")[0]
    before_root = session.get_area_root("before")
    after_root = session.get_area_root("after")
    html_relative_path = before_html.relative_to(before_root).as_posix()
    result = export_runtime_sources(
        page_builder=page_builder,
        output_directory=after_root,
        html_filename=html_relative_path,
    )
    print(str(result))

    session.save_in_after(result.html_path)
    for path in result.stylesheet_paths.values():
        session.save_in_after(path)

    return result

def _process_external_svg_decoration(
    session: Session,
    page_builder: PageBuilder,
    element: Element,
    original_ancestor_background_colors: Any,
    actual_ancestor_background_colors: Any,
    color_scheme: ColorScheme,
    processed_svg_files: dict[Path, Path],
) -> None:
    try:
        def transformed_reference(reference_value: str) -> str | None:
            svg_url = extract_url_value(reference_value)
            if svg_url is None or not is_svg_url(svg_url):
                return None

            raw_path = unquote(urlsplit(svg_url).path).replace("\\", "/")
            relative_path = raw_path.lstrip("/")
            svg_name = Path(relative_path).name if relative_path else Path(svg_url).name
            if not svg_name:
                return None

            before_root = session.get_area_root("before").resolve()
            candidate_root = (
                before_root
                if raw_path.startswith("/")
                else (page_builder.base_path or before_root)
            )
            svg_path = (candidate_root / relative_path).resolve()
            if (
                not svg_path.is_file()
                or not svg_path.is_relative_to(before_root)
            ):
                svg_path = session.get_path(svg_name, "before", "svg")

            glow_path = next(
                (
                    cached_path
                    for source_path, cached_path in processed_svg_files.items()
                    if source_path.exists() and svg_path.samefile(source_path)
                ),
                None,
            )
            if glow_path is None:
                glow_path = svg_path.with_name(
                    f"{svg_path.stem}-glow{svg_path.suffix}"
                )

                if not _rewrite_svg_file(
                    svg_path,
                    glow_path,
                    original_ancestor_background_colors,
                    actual_ancestor_background_colors,
                    color_scheme,
                ):
                    return None

                processed_svg_files[svg_path.resolve()] = glow_path
                session.save_in_before(glow_path)

            if page_builder.base_path is not None:
                try:
                    new_url = glow_path.resolve().relative_to(
                        page_builder.base_path.resolve(),
                        walk_up=True,
                    ).as_posix()
                except ValueError:
                    new_url = glow_path.name
            else:
                new_url = glow_path.name

            if re.search(r"url\(", reference_value, re.IGNORECASE):
                return re.sub(
                    r"url\(\s*(['\"]?)(.*?)\1\s*\)",
                    lambda match: (
                        f"url({match.group(1)}{new_url}{match.group(1)})"
                    ),
                    reference_value,
                    count=1,
                    flags=re.IGNORECASE,
                )

            return new_url

        for image_reference in element.image_references():
            source_value = (
                image_reference.value
                if isinstance(image_reference, Attribute)
                else image_reference.current_value
            )
            new_value = transformed_reference(source_value)
            if new_value is None or new_value == source_value:
                continue

            if isinstance(image_reference, Attribute):
                applied_value = page_builder.set_attribute_value(
                    element.node_id,
                    image_reference.name,
                    new_value,
                )
                image_reference.value = applied_value or new_value
            else:
                _transform_property(
                    page_builder,
                    element,
                    image_reference,
                    new_value,
                )
    except Exception as exc:
        exception_type = type(exc).__name__
        
        raise RuntimeError(
            f"Operation failed due to an unexpected error [{exception_type}]: {exc}"
        ) from exc


def _rewrite_svg_file(
    svg_path: Path,
    output_path: Path,
    original_ancestor_background_colors: Any,
    actual_ancestor_background_colors: Any,
    color_scheme: ColorScheme,
) -> bool:
    try:
        svg_content = svg_path.read_text(encoding="utf-8")
        clean_content = re.sub(r'xmlns="[^"]+"', '', svg_content, count=1)
        svg_root = ET.fromstring(clean_content)
        style_tag = svg_root.find(".//style")
        global_style = style_tag.text if style_tag is not None and style_tag.text else ""

        for elem in svg_root.iter():
            tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag_name in ("svg", "style", "defs", "metadata"):
                continue

            fill_defined = elem.get("fill") is not None

            for attr in ("fill", "stroke"):
                current_value = elem.get(attr)
                if not current_value or current_value.lower() == "none":
                    continue

                new_values = _differences(
                    attr,
                    get_colors(current_value),
                    original_ancestor_background_colors,
                    None,
                    actual_ancestor_background_colors,
                    None,
                    None,
                    color_scheme,
                    None,
                    None
                )
                if new_values:
                    elem.set(attr, str(new_values[0]))

            inline_style = elem.get("style", "")
            if inline_style:
                updated_style_parts = []
                for part in inline_style.split(";"):
                    if not part.strip() or ":" not in part:
                        if part.strip():
                            updated_style_parts.append(part.strip())
                        continue

                    prop, val = part.split(":", 1)
                    prop = prop.strip().lower()
                    val = val.strip()

                    if prop == "fill":
                        fill_defined = True

                    if prop in ("fill", "stroke") and val.lower() != "none":
                        new_values = _differences(
                            prop,
                            get_colors(val),
                            original_ancestor_background_colors,
                            None,
                            actual_ancestor_background_colors,
                            None,
                            None,
                            color_scheme,
                            None,
                            None
                        )
                        if new_values:
                            val = str(new_values[0])

                    updated_style_parts.append(f"{prop}: {val}")

                elem.set("style", "; ".join(updated_style_parts) + ";")

            selectors = [f".{c}" for c in (elem.get("class") or "").split()]
            if elem.get("id"):
                selectors.append(f"#{elem.get('id')}")

            for selector in selectors:
                if selector not in global_style:
                    continue

                block_match = re.search(rf"{selector}\s*\{{([^}}]+)\}}", global_style)
                if not block_match:
                    continue

                block_text = block_match.group(1)
                for prop in ("fill", "stroke"):
                    prop_match = re.search(rf"{prop}\s*:\s*([^;]+)", block_text)
                    if not prop_match:
                        continue

                    val = prop_match.group(1).strip()
                    if prop == "fill":
                        fill_defined = True

                    if val.lower() == "none":
                        continue

                    new_values = _differences(
                        prop,
                        get_colors(val),
                        original_ancestor_background_colors,
                        None,
                        actual_ancestor_background_colors,
                        None,
                        None,
                        color_scheme,
                        None,
                        None
                    )
                    if new_values:
                        global_style = global_style.replace(
                            prop_match.group(0),
                            f"{prop}: {new_values[0]}",
                        )

            if not fill_defined and tag_name in SVG_DEFAULT_FILL_TAGS:
                new_values = _differences(
                    "fill",
                    get_colors("rgb(0, 0, 0)"),
                    original_ancestor_background_colors,
                    None,
                    actual_ancestor_background_colors,
                    None,
                    None,
                    color_scheme,
                    None,
                    None
                )

                if new_values:
                    elem.set("fill", str(new_values[0]))

        if style_tag is not None and global_style:
            style_tag.text = global_style
            
        namespaces = dict(
            node
            for _, node in ET.iterparse(io.StringIO(svg_content), events=["start-ns"])
        )

        for prefix, uri in namespaces.items():
            ET.register_namespace(prefix, uri)
        ET.register_namespace("", "http://www.w3.org/2000/svg")

        if svg_root.tag == "svg" and "xmlns" not in svg_root.attrib:
            svg_root.set("xmlns", "http://www.w3.org/2000/svg")

        output_path.write_text(
            "<?xml version='1.0' encoding='utf-8'?>\n"
            + ET.tostring(
                svg_root,
                encoding="unicode",
                short_empty_elements=True,
            ),
            encoding="utf-8",
        )

        return True
    except Exception as exc:
        exception_type = type(exc).__name__
        
        raise RuntimeError(
            f"Operation failed due to an unexpected error [{exception_type}]: {exc}"
        ) from exc

def _transform_property(
    page_builder: PageBuilder,
    element: Element,
    property: Property | str,
    token_value: str
) -> None:
    if not element.node_id:
        return

    property_model = (
        property
        if isinstance(property, Property)
        else next(
            (
                item
                for item in element.properties
                if item.name == property
            ),
            None,
        )
    )

    if property_model is None:
        return

    if property_model.before_value != token_value:
        page_builder.set_effective_value(
            element.backend_node_id,
            element.node_id,
            property_model.name,
            token_value,
            element.tag_name,
        )
        changed_value = page_builder.current_property_value(
            element.node_id,
            property_model.name,
        )
        property_model.after_value = changed_value
        property_model.token_value = token_value
        property_model.has_color = bool(changed_value and get_colors(changed_value) is not None)

def _update_properties(
    page_builder: PageBuilder,
    element: Element,
) -> None:
    updated_properties = page_builder.get_computed_styles_for_node(
        element.node_id,
    )

    for property_model in element.properties:
        updated_value = updated_properties.get(property_model.name)
        property_model.after_value = updated_value if updated_value != property_model.before_value else None

def _text_contrast_target_tone(
    color_scheme: ColorScheme,
    actual_color: Color,
    actual_contrast_data: Any,
    actual_background_data: Any,
    original_contrast_data: Any,
    original_background_data: Any,
) -> Tone | None:
    palette, tone, _ = color_scheme.find_closest(actual_color, "palettes") or (None, None, None)
    if palette is None or tone is None:
        return None
    print("1")

    original_palette = None
    if original_contrast_data is not None:
        original_palette, _, _ = color_scheme.find_closest(
            original_contrast_data[1],
            "palettes",
        ) or (None, None, None)
    actual_palette, _, _ = color_scheme.find_closest(
        actual_contrast_data[1],
        "palettes",
    ) or (None, None, None)

    preserve_original_contrast = (
        original_contrast_data is not None
        and original_palette is not None
        and actual_palette is not None
        and original_contrast_data[2] >= original_contrast_data[3]
        and actual_palette.name == original_palette.name
    )
    print(str(preserve_original_contrast))
    print(str(actual_palette.name if actual_palette is not None else None))
    print(str(original_palette.name if original_palette is not None else None))
    print(str(original_palette.name if original_palette is not None else None))

    if actual_contrast_data[2] >= actual_contrast_data[3] and not preserve_original_contrast:
        print("entró")
        return None
    print("2")

    def valid_candidate(candidate_tone: Tone):
        contrast_ratio = candidate_tone.color.contrast(actual_contrast_data[1])
        if contrast_ratio <= actual_contrast_data[3]:
            return None

        return candidate_tone, contrast_ratio

    candidates = []
    candidate_tones = list(palette.tones)

    if palette.name == "Neutral":
        candidate_tones = [
            tone
            for tone in (
                palette.get_lowest_tone(),
                palette.get_highest_tone(),
            )
            if tone is not None
        ]

    print("candidate_tones=" + str([(tone.name, tone.value) for tone in candidate_tones]))

    target_contrast_ratio = (
        original_contrast_data[2]
        if original_contrast_data is not None
        else actual_contrast_data[3]
    )

    for candidate_tone in candidate_tones:
        print("3")

        candidate = valid_candidate(candidate_tone)
        if candidate is None:
            print(
                    "candidate_rejected="
                    + str(candidate_tone.name)
                    + " contrast="
                    + str(candidate_tone.color.contrast(actual_contrast_data[1]))
                    + " required="
                    + str(actual_contrast_data[3])
                )
            continue
        print("4")

        candidate_tone, contrast_ratio = candidate
        candidates.append(
            (
                abs(target_contrast_ratio - contrast_ratio),
                candidate_tone,
            )
        )

    if candidates:
        candidates.sort(key=lambda item: item[0])
        print(str(candidates))
        return candidates[0][1]

    print("5")
    return None

    return None

def _tone(color: Color) -> float:
    return float(color.convert("hct")["t"])

def _should_clean_shadow(colors: list[tuple[str, Color]] | None) -> bool:
    if not colors:
        return False

    return any(
        color.alpha(nans=False) < 0.5
        or _tone(color) < 50
        for _value, color in colors
    )

def _serialize_color(color: Color) -> str:
    return color.convert("srgb").to_string(
        fit={'method': 'raytrace', 'pspace': 'hct'},
        comma=True,
        alpha=True,
        rounding="decimal",
        precision=0
    )

def _get_maximum_contrast(
    foreground_colors: tuple[tuple[str, Color], ...],
    background_colors: tuple[tuple[str, Color], ...],
) -> float | None:
    """
    Calcula todos los contrastes posibles entre los colores del foreground
    y los colores del background.

    Devuelve el contraste máximo encontrado o None cuando alguna de las
    colecciones está vacía.
    """
    if not foreground_colors or not background_colors:
        return None

    return max(
        foreground.contrast(background)
        for _, foreground in foreground_colors
        for _, background in background_colors
    )

def _differences(property_name: str, property_colors: Any, original_ancestor_background_colors: Any, original_inner_background_colors: Any, actual_ancestor_background_colors: Any, actual_inner_background_colors: Any, tag_name: str | None, color_scheme: ColorScheme, start_range: Any, end_range: Any) -> list[Tone | str]:
    original_contrast = None
    target_values = []

    if property_colors is None or property_name is None or get_role(property_name) not in ("foreground", "background"):
        return target_values

    original_contrast = _get_maximum_contrast(property_colors, original_inner_background_colors if (original_inner_background_colors is not None and get_role(property_name) == "foreground") else original_ancestor_background_colors) 
    
    if original_contrast is not None:             
        for value, color in property_colors:
            if not color.is_nan("alpha") and (color.get("alpha") == 0 or is_css_value_contained("rgba(0, 0, 0, 0)", value)) :
                target_values.append(value)
                continue

            palette, tone, _steps = color_scheme.find_closest(color, "palettes") or (None, None, None)
            if palette is None or tone is None or (palette.name == "Neutral" and get_role(property_name) == "background" and tone.value <= 40 and tag_name not in SVG_PAINT_TAGS and tag_name is not None):
                target_values.append(value)
                continue

            differences = []

            lowest_tone = palette.get_lowest_tone()
            highest_tone = palette.get_highest_tone()
            lowest_value = int(start_range) if isinstance(start_range, int) else int(lowest_tone.value)
            highest_value = int(end_range) if isinstance(end_range, int) else int(highest_tone.value)

            for tone in palette.tones:
                if lowest_value <= int(tone.value) <= highest_value:
                    actual_external_contrast = _get_maximum_contrast([("", tone.color)], actual_inner_background_colors if (actual_inner_background_colors is not None and get_role(property_name) == "foreground") else actual_ancestor_background_colors)
                    difference = abs(actual_external_contrast - original_contrast) if actual_external_contrast is not None else None
                    if difference is not None:
                        differences.append((difference, tone))

            if not differences:
                target_values.append(_serialize_color(color))
                continue
                
            differences.sort(key=lambda item: item[0])
            target_tone = differences[0][1]
            target_values.append(target_tone if tag_name is not None else _serialize_color(target_tone.color))

    return target_values


def _original_backgrounds(root: Element, page_builder: PageBuilder) -> list[tuple[int, Any, Any, dict[str, Any]]]:
    original_backgrounds: list[tuple[int, Any, Any, dict[str, Any]]] = []
    background_data: dict[str, Any] = {}

    for element in root.iter_dfs():
        if element.has_text and not element.has_tag("body"):
            background_data = page_builder.get_background_colors(
                element.node_id
            ) or {}
        ancestor_background_property = None
        if element.category != "main-surface":
            effective_parent = element.get_effective_parent_background(root)
            ancestor_background_property = effective_parent.effective_background 

        element_background_property = element.effective_background
        inner_background_property = (
            element_background_property
            if element_background_property["name"]
            else ancestor_background_property
        )
        original_backgrounds.append(
            (
                element.backend_node_id,
                get_colors(ancestor_background_property["before_value"]) if ancestor_background_property is not None and ancestor_background_property["name"] else None,
                get_colors(inner_background_property["before_value"]) if inner_background_property is not None and inner_background_property["name"] else None,
                dict(background_data),
            )
        )

    return original_backgrounds

def _actual_backgrounds(root: Element, element: Element) -> Any:
    ancestor_background_property = None
    if element.category != "main-surface":
        effective_parent = element.get_effective_parent_background(root)
        ancestor_background_property = effective_parent.effective_background 

    ancestor_value = (
        ancestor_background_property["current_value"]
        if ancestor_background_property is not None and ancestor_background_property["name"]
        else None
    )

    element_background_property = element.effective_background
    inner_value = (
        element_background_property["current_value"]
        if element_background_property["name"] 
        else ancestor_value
    )

    return get_colors(ancestor_value), get_colors(inner_value)
