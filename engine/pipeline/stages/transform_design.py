from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.data.scope_css import CSSPROPERTIES
from engine.domain.data.scope_html_elements import get_html_element_category
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import (
    Color,
    ColorScheme,
    NEUTRAL_TONAL_STEPS,
    Palette,
    Tone,
    TONAL_STEPS,
)
from engine.domain.models.element import Element, Property
from engine.domain.models.session import Session
from engine.domain.models.summary import Summary
from engine.domain.utils.parsers import replace_property_values
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


CONTRACT = StageContract(
    name="transform_design",
    requires=(
        context_value(K.SESSION, Session),
        context_value(K.PAGE_BUILDER, PageBuilder),
        context_value(K.DOM_TREE, Element),
        context_value(K.COLOR_SCHEME, ColorScheme),
        context_value(K.SUMMARY, Summary),
    ),
    produces=(
        context_value(K.DOM_TREE, Element),
        context_value(K.SUMMARY, Summary),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    session = context.get(K.SESSION)
    page_builder = context.get(K.PAGE_BUILDER)
    root = context.get(K.DOM_TREE)
    color_scheme = context.get(K.COLOR_SCHEME)
    summary = context.get(K.SUMMARY)

    context.trace.add_stage_event(CONTRACT.name, "start")
    page_builder.set_color_scheme()

    elements = tuple(root.iter_bfs())
    element_registry = {
        element.backend_node_id: element
        for element in elements
    }

    for element in elements:
        if not element.node_id:
            continue

        category = get_html_element_category(element.tag_name)

        match category:
            case "main-surface":
                background_image = element.property("background-image")
                background_color = element.property("background-color")
                color = element.property("color")

                if background_image:
                    _transform_property(
                        page_builder,
                        element,
                        background_image.name,
                        "none",
                    )

                _transform_property(
                    page_builder,
                    element,
                    "background-color",
                    "rgb(0, 0, 0)",
                )

                _transform_property(
                    page_builder,
                    element,
                    "color",
                    "rgb(255, 255, 255)",
                )

            case (
                "container"
                | "input"
                | "decoration"
                | "composed"
                | "typography"
                | "media"
                | "other"
            ):
                surface_tone = None

                if category == "container":
                    surface_depth = max(element.depth or 1, 1)
                    surface_ancestor = element_registry.get(
                        element.parent_backend_node_id
                    )

                    while (
                        surface_ancestor is not None
                        and get_html_element_category(
                            surface_ancestor.tag_name
                        )
                        != "main-surface"
                    ):
                        has_background = any(
                            ancestor_property.has_color
                            and ancestor_property.name in CSSPROPERTIES
                            and CSSPROPERTIES[
                                ancestor_property.name
                            ].role
                            == "background"
                            and ancestor_property.get_colors()
                            for ancestor_property
                            in surface_ancestor.properties
                        )
                        if has_background:
                            break

                        surface_depth -= 1
                        surface_ancestor = element_registry.get(
                            surface_ancestor.parent_backend_node_id
                        )

                    surface_depth = max(surface_depth, 1)
                    surface_tone = TONAL_STEPS[
                        min(
                            surface_depth - 1,
                            len(TONAL_STEPS) - 1,
                        )
                    ]

                for css_property in element.properties:
                    if (
                        not css_property.has_color
                        or css_property.name not in CSSPROPERTIES
                    ):
                        continue

                    role = CSSPROPERTIES[css_property.name].role
                    if role not in ("background", "foreground"):
                        continue

                    if css_property.name == "color" and element.has_text:
                        continue

                    colors = css_property.get_colors()
                    if not colors:
                        continue

                    transformed_values = []

                    for value, color in colors:
                        tone = float(color.convert("hct")["t"])

                        match role:
                            case "background" if tone <= 40:
                                transformed_values.append(value)
                                continue
                            case "foreground" if tone >= 70:
                                transformed_values.append(value)
                                continue

                        closest_tone = min(
                            NEUTRAL_TONAL_STEPS,
                            key=lambda available_tone: abs(
                                available_tone - tone
                            ),
                        )

                        tone_index = NEUTRAL_TONAL_STEPS.index(
                            closest_tone
                        )

                        match category, role:
                            case "container", "background":
                                if surface_tone is None:
                                    raise ValueError(
                                        "Container surface tone "
                                        "was not calculated."
                                    )
                                target_tone = surface_tone

                            case _, "background":
                                target_tone = NEUTRAL_TONAL_STEPS[
                                    max(tone_index - 2, 0)
                                ]

                            case _, "foreground":
                                target_tone = NEUTRAL_TONAL_STEPS[
                                    min(
                                        tone_index + 2,
                                        len(NEUTRAL_TONAL_STEPS) - 1,
                                    )
                                ]

                            case _:
                                transformed_values.append(value)
                                continue

                        palette, _ = _resolve_tonal_color(
                            color_scheme,
                            color,
                        )
                        target_color = min(
                            palette.tones,
                            key=lambda palette_tone: abs(
                                palette_tone.value - target_tone
                            ),
                        ).color

                        transformed_values.append(
                            _serialize_color(
                                target_color
                                .clone()
                                .convert("srgb")
                                .set(
                                    "alpha",
                                    float(color.alpha(nans=False)),
                                )
                            )
                        )

                    after_value = replace_property_values(
                        css_property.before_value,
                        [value for value, _ in colors],
                        transformed_values,
                    )
                    _transform_property(
                        page_builder,
                        element,
                        css_property.name,
                        after_value,
                    )

                if not element.has_text:
                    continue

                background_data = page_builder.get_background_colors(
                    element.node_id
                )
                background_values = (
                    background_data["background_colors"] or ["black"]
                )

                contrast_data = element.get_text_contrast(
                    background_values,
                    background_data["font_size"] or "0px",
                    background_data["font_weight"] or 400,
                )
                if contrast_data is None:
                    continue

                (
                    foreground,
                    background,
                    contrast_ratio,
                    required_ratio,
                    _,
                ) = contrast_data

                if contrast_ratio >= required_ratio:
                    continue

                foreground_tone = float(
                    foreground.convert("hct")["t"]
                )
                background_is_dark = (
                    float(background.convert("hct")["t"]) < 55
                )
                transformed_color = None

                match foreground.is_achromatic():
                    case True:
                        palette, source_tone = _resolve_tonal_color(
                            color_scheme,
                            foreground,
                            force_neutral=True,
                        )
                        source_tone_index = min(
                            range(len(NEUTRAL_TONAL_STEPS)),
                            key=lambda index: abs(
                                NEUTRAL_TONAL_STEPS[index]
                                - source_tone.value
                            ),
                        )
                        opposite_tone = NEUTRAL_TONAL_STEPS[
                            -source_tone_index - 1
                        ]
                        palette_tones = sorted(
                            (
                                palette_tone
                                for palette_tone in palette.tones
                                if (
                                    palette_tone.value >= opposite_tone
                                    if background_is_dark
                                    else palette_tone.value <= opposite_tone
                                )
                            ),
                            key=lambda palette_tone: abs(
                                palette_tone.value - opposite_tone
                            ),
                        )

                        transformed_color = next(
                            (
                                palette_tone.color
                                .clone()
                                .convert("srgb")
                                .set("alpha", 1.0)
                                for palette_tone in palette_tones
                                if (
                                    palette_tone.color.contrast(background)
                                    >= required_ratio
                                )
                            ),
                            None,
                        )

                    case False:
                        for force_neutral in (False, True):
                            palette, _ = _resolve_tonal_color(
                                color_scheme,
                                foreground,
                                force_neutral=force_neutral,
                            )
                            palette_tones = sorted(
                                (
                                    palette_tone
                                    for palette_tone in palette.tones
                                    if (
                                        palette_tone.value >= 50
                                        if background_is_dark
                                        else palette_tone.value <= 50
                                    )
                                ),
                                key=lambda palette_tone: abs(
                                    palette_tone.value
                                    - foreground_tone
                                ),
                            )

                            transformed_color = next(
                                (
                                    palette_tone.color
                                    .clone()
                                    .convert("srgb")
                                    .set("alpha", 1.0)
                                    for palette_tone in palette_tones
                                    if (
                                        palette_tone.color.contrast(
                                            background
                                        )
                                        >= required_ratio
                                    )
                                ),
                                None,
                            )
                            if transformed_color is not None:
                                break

                if transformed_color is None:
                    transformed_color = next(
                        (
                            candidate
                            for candidate in (
                                Color("white"),
                                Color("black"),
                            )
                            if (
                                candidate.contrast(background)
                                >= required_ratio
                            )
                        ),
                        None,
                    )

                if transformed_color is None:
                    raise ValueError(
                        "No color satisfies the required text contrast."
                    )

                color_property = element.property("color")
                color_value = color_property.get_colors()[0][0]
                after_value = replace_property_values(
                    color_property.before_value,
                    [color_value],
                    [_serialize_color(transformed_color)],
                )
                _transform_property(
                    page_builder,
                    element,
                    color_property.name,
                    after_value,
                )

            case _:
                continue

    after_screenshot = session.get_path(
        "after.png",
        "artifacts",
        "png",
    )
    after_screenshot_path = page_builder.capture_fullpage_screenshot(
        output_path=after_screenshot
    )

    context.set(K.DOM_TREE, root)
    context.set(K.SUMMARY, summary)
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

    if before_value == after_value:
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
            )
        )
        return

    property_model.after_value = after_value


def _resolve_tonal_color(
    color_scheme: ColorScheme,
    source_color: Color,
    *,
    force_neutral: bool = False,
) -> tuple[Palette, Tone]:
    if force_neutral or source_color.is_achromatic():
        palette = color_scheme.get_palette("Neutral")
        if palette is None or not palette.tones:
            raise ValueError("The neutral palette is not available.")

        tone = min(
            palette.tones,
            key=lambda palette_tone: source_color.delta_e(
                palette_tone.color
            ),
        )
        return palette, tone

    closest_color = color_scheme.find_closest(
        source_color,
        "palettes",
    )
    if closest_color is None:
        raise ValueError("No tonal palette was found for the color.")

    palette, tone = color_scheme.resolve_color_location(
        closest_color
    )
    if palette is None or tone is None:
        raise ValueError(
            "The closest color does not belong to a tonal palette."
        )

    return palette, tone


def _serialize_color(color: Color) -> str:
    srgb = color.convert("srgb").fit("srgb")
    return srgb.to_string(
        comma=True,
        alpha=float(srgb.alpha(nans=False)) < 0.999,
    )
