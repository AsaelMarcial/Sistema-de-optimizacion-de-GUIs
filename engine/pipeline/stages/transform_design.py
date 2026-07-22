from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.data.scope_css import CSSPROPERTIES
from engine.domain.data.scope_html_elements import get_html_element_category
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import (
    Color,
    ColorScheme,
    NEUTRAL_TONAL_STEPS,
    TONAL_STEPS,
)
from engine.domain.models.element import Element, Property
from engine.domain.models.session import Session
from engine.domain.utils.parsers import get_colors, is_gradient, is_url_image, replace_property_values
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

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

    context.trace.add_stage_event(CONTRACT.name, "start")
    page_builder.set_color_scheme()

    for element in root.iter_bfs():
        if not element.node_id:
            continue

        _update_properties(page_builder, element)

        category = get_html_element_category(element.tag_name)

        parent_background = None
        if category != "main-surface":
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

        for css_property in tuple(element.properties):
            property_data = CSSPROPERTIES.get(css_property.name)
            if property_data is None:
                continue

            role = property_data.role

            match category, role:
                case "main-surface", "background":

                    if css_property.name == "background-image":
                        _clean_property(
                            page_builder,
                            element,
                            "background-image"
                        )

                    if css_property.name == "background-color" and css_property.before_value == "rgb(0, 0, 0)":
                        continue

                    _transform_property(
                        page_builder,
                        element,
                        "background-color",
                        "rgb(0, 0, 0)",
                    )

                case "container", "background":
                    if element.has_image:
                        continue
                    
                    if css_property.name == "background-image":
                        _clean_property(
                            page_builder,
                            element,
                            "background-image",
                        )

                    if element.tag_name == "footer" or element.tag_name == "header":
                        _clean_property(
                            page_builder,
                            element,
                            "background-color",
                        )
                        continue

                    neutral_palette = color_scheme.get_palette("Neutral")
                    before_colors = get_colors(css_property.before_value)
                    if neutral_palette is None or not before_colors:
                        continue

                    neutral_40 = neutral_palette.tone(40)
                    if neutral_palette is None or neutral_40 is None or not before_colors:
                        continue

                    tone_color = neutral_40.color

                    before_color = before_colors[0][1].convert("hct")
                        
                    if before_color["t"] <= tone_color["t"] and before_colors[0][1].is_achromatic() and not is_gradient(css_property.before_value) :
                        continue

                    if (
                        parent_background_colors
                        and _serialize_color(parent_background_colors[0][1].convert("hct")) == _serialize_color(before_color)
                    ):
                        _clean_property(
                            page_builder,
                            element,
                            "background-color",
                        )
                        continue

                    if element.tag_name == "nav":
                        before_color["c"] = 0
                        closest = color_scheme.find_closest(before_color, "Neutral")
                        _, tone = color_scheme.resolve_color_location(closest)
                        target_color = tone.color
                        if before_color["t"] >= tone_color["t"]:
                            tone_index = NEUTRAL_TONAL_STEPS.index(tone.value)
                            opposite_index = len(NEUTRAL_TONAL_STEPS) - tone_index - 1
                            reversed_tone = neutral_palette.tone(NEUTRAL_TONAL_STEPS[opposite_index])
                            target_color = reversed_tone.color

                        _transform_property(
                            page_builder,
                            element,
                            "background-color",
                            _serialize_color(target_color),
                        )
                        continue

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
                        if 10 <= tone <= 50
                    )

                    target_tone = elevation_tones[
                        min(
                            max(surface_depth, 1) - 1,
                            len(elevation_tones) - 1,
                        )
                    ]

                    best_tone = neutral_palette.tone(int(target_tone))
                    
                    if best_tone is None:
                        continue

                    _transform_property(
                        page_builder,
                        element,
                        "background-color",
                        _serialize_color(best_tone.color),
                    )

                case "input", "foreground" | "background" :
                    _clean_property(
                        page_builder,
                        element,
                        css_property.name
                    )

                case "composed" | "typography" | "decoration", "background":
                    if element.has_image:
                        continue

                    colors = get_colors(css_property.before_value)

                    if not colors:
                        continue

                    actual_parent_colors = (
                        get_colors(parent_background.after_value)
                        if parent_background is not None and parent_background.after_value
                        else parent_background_colors
                    )

                    if not actual_parent_colors or original_external_contrast is None:
                        continue

                    target_colors = []
                    for _value, color in colors:
                        closest = color_scheme.find_closest(color, "palettes")
                        palette, _ = color_scheme.resolve_color_location(closest)
                        if palette is None:
                            target_colors.append(_serialize_color(color))
                            continue

                        differences = []

                        for tone in palette.tones:
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
                            target_colors.append(_serialize_color(color))
                            continue

                        differences.sort(key=lambda item: item[0])
                        target_tone = differences[1][1] if len(differences) > 1 else differences[0][1]
                        target_colors.append(_serialize_color(target_tone.color))

                    print("Target colors: " + str(target_colors))

                    after_value = replace_property_values(
                        css_property.before_value,
                        [value for value, _color in colors],
                        target_colors,
                    )

                    print("After value: " + str(after_value))

                    #print(str(actual_value) + " " + str(after_value))
                    _transform_property(
                        page_builder,
                        element,
                        css_property.name,
                        after_value,
                    )

                case "main-surface" | "container" | "composed" | "typography" | "decoration" | "media" , "foreground":
                    actual_value = css_property.after_value if css_property.has_changed else css_property.before_value
                    if css_property.has_color:
                        colors = get_colors(actual_value)

                    if category == "main-surface" and css_property.name == "color" and actual_value != "rgb(255, 255, 255)":
                        _transform_property(
                            page_builder,
                            element,
                            "color",
                            "rgb(255, 255, 255)",
                        )
                        continue

                    if (
                        css_property.name in ("text-shadow", "box-shadow")
                        and _should_clean_shadow(colors)
                    ):
                        _clean_property(
                            page_builder,
                            element,
                            css_property.name
                        )
                        continue

                    if css_property.name == "color":
                        continue

                    if colors:
                        after_value = replace_property_values(
                            actual_value,
                            [value for value, _color in colors],
                            [
                                _serialize_color(
                                    _set_tone(
                                        color,
                                        _inverted_tone(color),
                                        NEUTRAL_TONAL_STEPS,
                                        hct_min=0.0,
                                        hct_max=100.0,
                                    )
                                )
                                for _value, color in colors
                            ],
                        )
                        _transform_property(
                            page_builder,
                            element,
                            css_property.name,
                            after_value,
                        )

                case _,_:
                    continue

        if element.has_text and element.property("font-size") is not None and element.property("font-weight") is not None:
            background_data = page_builder.get_background_colors(
                element.node_id
            ) or {}

            contrast_data = element.get_text_contrast(
                background_data.get("background_colors") or None,
                background_data.get("font_size") or (
                    element.property("font-size").after_value
                    if element.property("font-size").has_changed
                    else element.property("font-size").before_value
                ),
                background_data.get("font_weight") or (
                    element.property("font-weight").after_value
                    if element.property("font-weight").has_changed
                    else element.property("font-weight").before_value
                ),
            )

            if contrast_data is None:
                _clean_property(
                    page_builder,
                    element,
                    "color"
                )
                continue

            (
                foreground,
                background,
                contrast_ratio,
                required_ratio,
                is_large_text,
            ) = contrast_data

            if contrast_ratio >= required_ratio:
                continue # si ya lo cumple no pasa nada

            color_property = element.property("color")
            color_value = (
                color_property.after_value
                if color_property is not None and color_property.has_changed
                else color_property.before_value
                if color_property is not None
                else ""
            )

            if color_value and Color(color_value).is_achromatic():
                continue #aquí se reemplazaría continue por la lógica de inversión en el tono de cada color. Si no se cumple a la primera se irá disminuyendo o aumentando un tono por iteración. Hay que usar un while que se rompa al cumplir con el contraste requerido.
            elif color_value and not Color(color_value).is_achromatic():
                continue #aquí se reemplazaría continue por la lógica de aumento (si se necesita aclarar para mejorar el contraste) o disminución 1 tono (si se necesita oscurecer para mejorar el contraste) a la vez hasta llegar al contraste requerido.Hay que usar un while que se rompa al cumplir con el contraste requerido.

        _update_properties(page_builder, element)
    after_screenshot = session.get_path(
        "after.png",
        "artifacts",
        "png",
    )
    after_screenshot_path = page_builder.capture_fullpage_screenshot(
        output_path=after_screenshot
    )

    context.set(K.DOM_TREE, root)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {"after_screenshot_path": after_screenshot_path},
    )
    return context


def _transform_property(
    page_builder: PageBuilder,
    element: Element,
    property_name: str,
    after_value: str,
) -> None:
    if not element.node_id:
        return

    property_model = element.property(property_name)
    before_value = property_model.before_value if property_model is not None else ""
    current_value = (
        property_model.after_value
        if property_model is not None and property_model.has_changed
        else before_value
    )

    if current_value == after_value:
        return

    page_builder.set_effective_value(
        element.node_id,
        property_name,
        after_value,
    )

    if property_model is None:
        element.properties.append(
            Property(
                name=property_name,
                before_value="",
                after_value=after_value,
                has_color=bool(get_colors(after_value)),
            )
        )
        return

    property_model.after_value = after_value
    property_model.has_color = property_model.has_color or bool(
        get_colors(after_value)
    )

def _clean_property(
    page_builder: PageBuilder,
    element: Element,
    property_name: str,
) -> None:
    if not element.node_id:
        return

    property_model = element.property(property_name)
    if property_model is None:
        return

    page_builder.clean_property_value(
        element.node_id,
        property_name,
    )

    property_model.after_value = None

def _update_properties(
    page_builder: PageBuilder,
    element: Element,
) -> None:
    updated_properties = page_builder.get_computed_styles_for_node(
            element.node_id,
    )

    for property_model in element.properties:
        updated_value = updated_properties.get(property_model.name)
        if updated_value is None:
            continue

        property_model.after_value = (
            updated_value
            if updated_value != property_model.before_value
            else None
        )

def _tone(color: Color) -> float:
    try:
        return float(color.convert("hct")["t"])
    except Exception:
        return 0.0


def _inverted_tone(color: Color) -> int:
    tone_index = min(
        range(len(NEUTRAL_TONAL_STEPS)),
        key=lambda index: abs(
            _scale_step_to_hct_tone(
                NEUTRAL_TONAL_STEPS[index],
                NEUTRAL_TONAL_STEPS,
                hct_min=0.0,
                hct_max=100.0,
            )
            - _tone(color)
        ),
    )
    return NEUTRAL_TONAL_STEPS[-tone_index - 1]


def _set_tone(
    color: Color,
    target_tone: int,
    tone_steps: tuple[int, ...] = TONAL_STEPS,
    *,
    hct_min: float = 10.0,
    hct_max: float = 95.0,
) -> Color:
    return (
        color
        .convert("hct")
        .clone()
        .set(
            "tone",
            _scale_step_to_hct_tone(
                target_tone,
                tone_steps,
                hct_min=hct_min,
                hct_max=hct_max,
            ),
        )
        .fit("srgb", method="raytrace", pspace="hct")
        .convert("srgb")
        .set("alpha", float(color.alpha(nans=False)))
    )


def _scale_step_to_hct_tone(
    step: int,
    steps: tuple[int, ...],
    *,
    hct_min: float = 10.0,
    hct_max: float = 95.0,
) -> float:
    min_step = min(steps)
    max_step = max(steps)
    if min_step == max_step:
        return (hct_min + hct_max) / 2

    ratio = (int(step) - min_step) / (max_step - min_step)
    return hct_min + (ratio * (hct_max - hct_min))


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
