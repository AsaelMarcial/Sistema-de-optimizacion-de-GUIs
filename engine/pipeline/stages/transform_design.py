from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.data.scope_css import CSSPROPERTIES
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import (
    Color,
    ColorScheme,
    NEUTRAL_TONAL_STEPS,
    TONAL_STEPS,
)
from engine.domain.models.element import Element, Property
from engine.domain.models.session import Session
from engine.domain.models.token import TokenInventory
from engine.domain.utils.css_generator import generate_theme_css
from engine.domain.utils.parsers import (
    cache_busted_url,
    extract_url_value,
    get_colors,
    is_gradient,
    is_svg_url,
    replace_property_values,
)
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlsplit
import re
import io

SVG_PAINT_TAGS = ("svg", "circle", "rect", "ellipse", "line", "polyline", "polygon", "path")
SVG_DEFAULT_FILL_TAGS = ("path", "circle", "rect", "ellipse", "polygon", "polyline", "text", "use")

def _transformed_dom_tree_ready(root: Element) -> bool:
    try:
        for element in root.iter_bfs():
            if element.tag_name != "body":
                continue

            background_color = element.property("background-color")
            color = element.property("color")

            background_value = (
                background_color.after_value
                if background_color.has_changed
                else background_color.before_value
            )
            color_value = (
                color.after_value
                if color.has_changed
                else color.before_value
            )
            return (
                background_value == "rgb(0, 0, 0)"
                and color_value == "rgb(255, 255, 255)"
            )

        return False
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False

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
    processed_svg_files: dict[Path, str] = {}

    for element in root.iter_dfs():
        if not element.node_id:
            continue
        
        _update_properties(page_builder, element)

        parent_background = None
        if element.category != "main-surface":
            effective_parent = element.get_effective_parent_background(root)
            parent_background = (
                effective_parent.effective_background
                if effective_parent is not None
                else None
            ) 

        inner_background = element.effective_background
        if inner_background is None:
            inner_background = parent_background

        inner_background_colors = (
            get_colors(inner_background.before_value)
            if inner_background is not None
            else None
        )
        parent_background_colors = (
            get_colors(parent_background.before_value)
            if parent_background is not None
            else None
        )

        original_external_contrast = _get_maximum_contrast(
            inner_background_colors,
            parent_background_colors,
        )

        actual_parent_colors = (
            get_colors(parent_background.after_value)
            if parent_background is not None and parent_background.after_value
            else parent_background_colors
        )

        if (
            element.category == "decoration"
            and element.tag_name not in SVG_PAINT_TAGS
            and actual_parent_colors
        ):
            _process_external_svg_decoration(
                session,
                page_builder,
                element,
                actual_parent_colors,
                original_external_contrast,
                color_scheme,
                processed_svg_files,
            )

        for css_property in tuple(element.properties):
            property_data = CSSPROPERTIES.get(css_property.name)
            if property_data is None or css_property.has_color is False:
                continue

            before_colors = get_colors(css_property.before_value)

            match element.category, property_data.role:
                case "main-surface", "background":
                    if css_property.name == "background-image":
                        _transform_property(
                            page_builder,
                            element,
                            "background-image",
                            "none"
                        )

                    _transform_property(
                        page_builder,
                        element,
                        "background-color",
                        "var(--Neutral-0)"
                    )

                case "container", "background":
                    if element.has_image:
                        continue
                    elif css_property.name == "background-image":
                        _transform_property(
                            page_builder,
                            element,
                            "background-image",
                            "none"
                        )

                    neutral_palette = color_scheme.get_palette("Neutral")
                    before_color = before_colors[0][1].convert("hct")

                    if (element.tag_name == "footer" or element.tag_name == "header") or (parent_background_colors and _serialize_color(parent_background_colors[0][1].convert("hct")) == _serialize_color(before_color)):
                        _clean_property(
                            page_builder,
                            element,
                            "background-color",
                        )
                        continue
                        
                    if before_color["t"] <= 40 and before_colors[0][1].is_achromatic() and not is_gradient(css_property.before_value) :
                        continue

                    target_tone = None

                    if element.tag_name == "nav":
                        closest = color_scheme.find_closest(before_color, "Neutral")
                        _, tone = color_scheme.resolve_color_location(closest)

                        target_tone = tone

                        if before_color["t"] >= 40:
                            tone_index = NEUTRAL_TONAL_STEPS.index(int(tone.value))
                            opposite_index = len(NEUTRAL_TONAL_STEPS) - tone_index - 1
                            target_tone = neutral_palette.tone(NEUTRAL_TONAL_STEPS[opposite_index])
                    else:
                        surface_depth = max(element.depth or 1, 1)
                        for surface_ancestor in root.ancestors_of(element):
                            if surface_ancestor.tag_name == "body":
                                break
                            
                            if surface_ancestor.effective_background is not None and Color(surface_ancestor.effective_background.before_value)["alpha"] >= 0.1:
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

                    if target_tone is None:
                        continue

                    _transform_property(
                        page_builder,
                        element,
                        "background-color",
                        target_tone.to_var
                    )

                case "input", "foreground" | "background" :
                    _clean_property(
                        page_builder,
                        element,
                        css_property.name
                    )

                case "composed" | "typography", "background":
                    if element.has_image:
                        continue

                    actual_parent_colors = (
                        get_colors(parent_background.after_value)
                        if parent_background is not None and parent_background.after_value
                        else parent_background_colors
                    )

                    if not actual_parent_colors or original_external_contrast is None:
                        continue

                    target_token_values = []
                    
                    for _value, color in before_colors:
                        closest = color_scheme.find_closest(color, "palettes")
                        palette, tone = color_scheme.resolve_color_location(closest)
                        if closest is None or palette is None or tone is None:
                            target_token_values.append(_serialize_color(color))
                            continue

                        if palette.name == "Neutral":
                            if closest["t"] >= 40:
                                tone_index = NEUTRAL_TONAL_STEPS.index(int(tone.value))
                                opposite_index = (len(NEUTRAL_TONAL_STEPS) - 1) - tone_index
                                target_tone = palette.tone(NEUTRAL_TONAL_STEPS[opposite_index])
                            else:
                                target_tone = tone
                            if target_tone is None:
                                target_token_values.append(_serialize_color(color))
                                continue
                            target_token_values.append(target_tone.to_var)
                            continue

                        differences = []

                        for tone in palette.tones:
                            if 30 <= int(tone.value) <= 80:
                                actual_external_contrast = _get_maximum_contrast(
                                    [("", tone.color)],
                                    actual_parent_colors,
                                )

                                if actual_external_contrast is None:
                                    continue

                                difference = abs(
                                    actual_external_contrast
                                    - original_external_contrast
                                )
                                differences.append((difference, tone))

                        if not differences:
                            target_token_values.append(_serialize_color(color))
                            continue

                        differences.sort(key=lambda item: item[0])
                        target_tone = differences[1][1] if len(differences) > 1 else differences[0][1]
                        target_token_values.append(target_tone.to_var)

                    token_value = replace_property_values(
                        css_property.before_value,
                        [value for value, _color in before_colors],
                        target_token_values,
                    )

                    _transform_property(
                        page_builder,
                        element,
                        css_property.name,
                        token_value
                    )

                case "main-surface" | "container" | "composed" | "typography" | "media" , "foreground":
                    if element.category == "main-surface" and css_property.name == "color" and css_property.before_value != "rgb(255, 255, 255)":
                        _transform_property(
                            page_builder,
                            element,
                            "color",
                            "var(--Neutral-100)"
                        )
                        continue

                    if (
                        css_property.name in ("text-shadow", "box-shadow")
                        and _should_clean_shadow(before_colors)
                    ):
                        _clean_property(
                            page_builder,
                            element,
                            css_property.name
                        )
                        continue

                    if css_property.name == "color":
                        continue

                    target_token_values = []

                    for _value, color in before_colors:
                        closest = color_scheme.find_closest(color, "palettes")
                        palette, tone = color_scheme.resolve_color_location(closest)
                        if closest is None or palette is None or tone is None:
                            target_token_values.append(_serialize_color(color))
                            continue

                        steps = NEUTRAL_TONAL_STEPS if palette.name == "Neutral" else TONAL_STEPS

                        counter = 3
                        next_tone = tone
                        if len(before_colors) == 1 and palette.name == "Neutral":
                            target_tone = palette.tone(100)
                            if target_tone is None:
                                continue
                            target_token_value = target_tone.to_var
                        elif int(tone.value) < 50:
                            target_token_value = tone.to_var
                            while counter >= 1:
                                next_tone = palette.next_tone(int(next_tone.value))
                                if next_tone is None:
                                    break
                                tone_index = steps.index(int(next_tone.value))
                                target_tone = palette.tone(steps[tone_index])
                                if target_tone is None:
                                    break
                                target_token_value = target_tone.to_var
                                counter -= 1                           
                        else:
                            target_token_value = tone.to_var

                        target_token_values.append(target_token_value)

                    token_value = replace_property_values(
                        css_property.before_value,
                        [value for value, _color in before_colors],
                        target_token_values,
                    )

                    _transform_property(
                        page_builder,
                        element,
                        css_property.name,
                        token_value
                    )

                case "decoration", "foreground" | "background":
                    if element.tag_name in SVG_PAINT_TAGS:
                        target_values = _process_decorations(
                            before_colors,
                            actual_parent_colors,
                            original_external_contrast,
                            element.tag_name,
                            color_scheme,
                        )
                        if target_values:
                            token_value = replace_property_values(
                                css_property.before_value,
                                [value for value, _color in before_colors],
                                target_values,
                            )
                            _transform_property(
                                page_builder,
                                element,
                                css_property.name,
                                token_value
                            )

                case _,_:
                    continue

        if element.has_text and element.tag_name != "body":
            background_data = page_builder.get_background_colors(
                element.node_id
            ) or {}

            color_property = element.property("color")

            if color_property is not None and background_data.get("background_colors") is not None and background_data.get("font_size") is not None and background_data.get("font_weight") is not None:

                contrast_data = element.get_text_contrast(
                    color_property.after_value if color_property.has_changed else color_property.before_value,
                    background_data.get("background_colors"),
                    background_data.get("font_size"),
                    background_data.get("font_weight"),
                )
                if contrast_data is not None:

                    (
                        _,
                        background,
                        contrast_ratio,
                        required_ratio,
                        _,
                    ) = contrast_data

                    if contrast_ratio < required_ratio:
                        target_tone = _text_contrast_target_tone(
                            color_scheme,
                            Color(color_property.after_value if color_property.has_changed else color_property.before_value),
                            background,
                            required_ratio,
                        )
                        if target_tone is not None:
                            _transform_property(
                                page_builder,
                                element,
                                "color",
                                target_tone.to_var
                            )
        _update_properties(page_builder, element)

    css_path = _theme_css_path(session)
    token_inventory.generate_property_tokens(root)
    root_css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    css_path.write_text(
        root_css.rstrip()
        + "\n\n"
        + generate_theme_css(token_inventory.property_tokens),
        encoding="utf-8",
    )
    session.save_in_before(css_path)
    data_theme_ready = page_builder.set_data_theme()
    theme_link_ready = page_builder.set_theme_link()
    
    for token in token_inventory.property_tokens.values():
        for element_id, property_name in token.element_ids:
            page_builder.set_effective_value(
                element_id,
                property_name,
                token.to_var,
            )

    after_screenshot = session.get_path(
        "after.png",
        "artifacts",
        "png",
    )
    after_screenshot_path = page_builder.capture_fullpage_screenshot(
        output_path=after_screenshot
    )
    after_html_path = _persist_runtime_html(session, page_builder)

    context.set(K.DOM_TREE, root)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "after_screenshot_path": after_screenshot_path,
            "after_html_path": str(after_html_path),
            "data_theme_ready": data_theme_ready,
            "theme_link_ready": theme_link_ready,
        },
    )
    return context


def _theme_css_path(session: Session):
    html_file = session.find_by_suffix("before", ("html",))[0]
    return html_file.parent / "glow.css"


def _persist_runtime_html(session: Session, page_builder: PageBuilder):
    before_html = session.find_by_suffix("before", ("html",))[0]
    after_html = session.get_path(
        before_html.name,
        "after",
        before_html.suffix,
    )
    after_html.write_text(
        page_builder.get_runtime_html(),
        encoding="utf-8",
    )
    session.save_in_after(after_html)
    return after_html

def _process_external_svg_decoration(
    session: Session,
    page_builder: PageBuilder,
    element: Element,
    actual_parent_colors,
    original_external_contrast,
    color_scheme: ColorScheme,
    processed_svg_files: dict[Path, str],
) -> None:
    print(element.tag_name)
    before_root = session.get_area_root("before")

    for svg_reference in element.image_references():
        svg_url = extract_url_value(svg_reference)
        if svg_url is None or not is_svg_url(svg_url):
            continue

        raw_path = unquote(urlsplit(svg_url).path).replace("\\", "/")
        relative_path = raw_path.lstrip("/")
        svg_path = (before_root / relative_path).resolve() if relative_path else None
        print(str(svg_url))
        print(str(raw_path))
        print(str(relative_path))
        print(str(svg_path))
        if svg_path is None or not svg_path.is_file():
            svg_name = Path(relative_path).name if relative_path else Path(svg_url).name
            print(str(svg_name))
            if not svg_name:
                continue

            try:
                svg_path = session.get_path(svg_name, "before", "svg")
                print(str(svg_path))
                
            except (FileNotFoundError, ValueError):
                continue

        cache_key = svg_path.resolve()
        print(str(cache_key))
        version = processed_svg_files.get(cache_key)
        if version is None:
            if not _rewrite_svg_file(
                svg_path,
                actual_parent_colors,
                original_external_contrast,
                color_scheme,
            ):
                continue

            version = f"glow={len(processed_svg_files) + 1}"
            processed_svg_files[cache_key] = version

        try:
            page_builder.refresh_image_reference(
                element.node_id,
                svg_reference,
                cache_busted_url(svg_url, version),
            )
        except RuntimeError:
            continue


def _rewrite_svg_file(
    svg_path: Path,
    actual_parent_colors,
    original_external_contrast,
    color_scheme: ColorScheme,
) -> bool:
    try:
        svg_content = svg_path.read_text(encoding="utf-8")
        clean_content = re.sub(r'xmlns="[^"]+"', '', svg_content, count=1)
        svg_root = ET.fromstring(clean_content)
    except (OSError, ET.ParseError):
        return False

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

            new_values = _process_decorations(
                get_colors(current_value),
                actual_parent_colors,
                original_external_contrast,
                tag_name,
                color_scheme,
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
                    new_values = _process_decorations(
                        get_colors(val),
                        actual_parent_colors,
                        original_external_contrast,
                        tag_name,
                        color_scheme,
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

                new_values = _process_decorations(
                    get_colors(val),
                    actual_parent_colors,
                    original_external_contrast,
                    tag_name,
                    color_scheme,
                )
                if new_values:
                    global_style = global_style.replace(
                        prop_match.group(0),
                        f"{prop}: {new_values[0]}",
                    )

        if not fill_defined and tag_name in SVG_DEFAULT_FILL_TAGS:
            new_values = _process_decorations(
                get_colors("rgb(0, 0, 0)"),
                actual_parent_colors,
                original_external_contrast,
                tag_name,
                color_scheme,
            )
            if new_values:
                elem.set("fill", str(new_values[0]))

    if style_tag is not None and global_style:
        style_tag.text = global_style

    try:
        namespaces = dict(
            node
            for _, node in ET.iterparse(io.StringIO(svg_content), events=["start-ns"])
        )
    except ET.ParseError:
        namespaces = {}

    for prefix, uri in namespaces.items():
        ET.register_namespace(prefix, uri)
    ET.register_namespace("", "http://www.w3.org/2000/svg")

    if svg_root.tag == "svg" and "xmlns" not in svg_root.attrib:
        svg_root.set("xmlns", "http://www.w3.org/2000/svg")

    try:
        svg_path.write_text(
            "<?xml version='1.0' encoding='utf-8'?>\n"
            + ET.tostring(
                svg_root,
                encoding="unicode",
                short_empty_elements=True,
            ),
            encoding="utf-8",
        )
    except OSError:
        return False

    return True


def _transform_property(
    page_builder: PageBuilder,
    element: Element,
    property_name: str,
    token_value: str
) -> None:
    if not element.node_id:
        return

    property_model = element.property(property_name)
    if property_model is None:
        property_model = Property(
            name=property_name,
            before_value="",
        )
        property_model.has_color = bool(
            property_model.before_value and get_colors(property_model.before_value)
        ) or bool(
            property_model.after_value and get_colors(property_model.after_value)
        )
        element.properties.append(property_model)

    page_builder.set_effective_value(
        element.node_id,
        property_name,
        token_value,
    )

    property_model.token_value = token_value 

def _clean_property(
    page_builder: PageBuilder,
    element: Element,
    property_name: str,
) -> None:
    if not element.node_id:
        return

    property_model = element.property(property_name)
    if property_model is None:
        property_model = Property(name=property_name)
        element.properties.append(property_model)

    changed_value = page_builder.clean_property_value(
        element.node_id,
        property_name,
    )

    property_model.after_value = (
        changed_value
        if changed_value != property_model.before_value
        else None
    )
    property_model.has_color = False if property_model.after_value is None else bool(get_colors(property_model.after_value))

def _update_properties(
    page_builder: PageBuilder,
    element: Element,
) -> None:
    updated_properties = page_builder.get_computed_styles_for_node(
        element.node_id,
    )

    for property_model in element.properties:
        updated_value = updated_properties.get(property_model.name)
        if updated_value is not None:
            property_model.after_value = (
                updated_value
                if updated_value != property_model.before_value
                else None
            )

def _text_contrast_target_tone(
    color_scheme: ColorScheme,
    actual_color: Color,
    background: Color,
    required_ratio: float,
):
    closest = color_scheme.find_closest(actual_color, "palettes")
    palette, tone = color_scheme.resolve_color_location(closest)

    if palette is None or tone is None:
        return None

    steps = (
        NEUTRAL_TONAL_STEPS
        if palette.name == "Neutral"
        else TONAL_STEPS
    )

    tone_value = int(tone.value)
    if tone_value not in steps:
        return None

    candidate_index = steps.index(tone_value)

    if palette.name == "Neutral":
        candidate_index = len(steps) - candidate_index - 1
        candidate_tone = palette.tone(steps[candidate_index])

        if (
            candidate_tone is not None
            and candidate_tone.color.contrast(background) >= required_ratio
        ):
            return candidate_tone

        reference_color = (
            candidate_tone.color
            if candidate_tone is not None
            else actual_color
        )
    else:
        reference_color = actual_color

    direction = (
        1
        if _tone(reference_color) > _tone(background)
        else -1
    )

    candidate_index += direction

    while 0 <= candidate_index < len(steps):
        candidate_tone = palette.tone(steps[candidate_index])

        if (
            candidate_tone is not None
            and candidate_tone.color.contrast(background) >= required_ratio
        ):
            return candidate_tone

        candidate_index += direction

    return None

def _tone(color: Color) -> float:
    try:
        return float(color.convert("hct")["t"])
    except Exception:
        return 0.0

def _should_clean_shadow(colors: list[tuple[str, Color]] | None) -> bool:
    if not colors:
        return False

    return any(
        color.alpha(nans=False) < 0.5
        or _tone(color) < 200
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

def _process_decorations(colors: any, actual_parent_colors: any, original_external_contrast: any, tag_name: str, color_scheme: ColorScheme) -> list[str] | None:
    if not colors:
        return None

    target_values = []
                    
    for _value, color in colors:
        closest = color_scheme.find_closest(color, "palettes")
        palette, tone = color_scheme.resolve_color_location(closest)
        if closest is None or palette is None or tone is None:
            target_values.append(_serialize_color(color))
            continue

        if palette.name == "Neutral":
            target_tone = palette.tone(100)
        else:
            differences = []

            for tone in palette.tones:
                if 60 <= int(tone.value):
                    actual_external_contrast = _get_maximum_contrast([("", tone.color)], actual_parent_colors,)

                    if actual_external_contrast is None:
                        continue

                    difference = abs(
                        actual_external_contrast
                        - original_external_contrast
                    )
                    differences.append((difference, tone))

            if not differences:
                target_values.append(_serialize_color(color))
                continue
            
            differences.sort(key=lambda item: item[0])
            target_tone = differences[0][1]
        target_values.append(target_tone.to_var if tag_name in ("svg", "circle", "rect", "ellipse", "line", "polyline", "polygon", "path") else _serialize_color(target_tone.color))

    return target_values
