from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.utils.palette_preview import render_palette_preview
from engine.adapters.utils.pixel import build_histogram, image_to_array
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import Color, ColorScheme
from engine.domain.models.element import Element
from engine.domain.models.session import Session
from engine.domain.models.summary import Summary
from engine.domain.utils.parsers import is_gradient
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.domain.data.scope_html_elements import get_html_element_category

_MEDIA_TAGS = {
    "img",
    "picture",
    "source",
    "video",
    "image",
    "canvas",
    "object",
    "embed",
}
_PREDOMINANT_COLOR_LIMIT = 13
_FAMILY_HUE_DELTA_THRESHOLD = 25
_FAMILY_CHROMA_DELTA_THRESHOLD = 50


def _summary_ready(summary: Summary) -> bool:
    try:
        required_overviews = (
            "environmental_color_histogram",
            "design_color_histogram",
            "colors_distribution",
            "predominant_colors",
        )
        return all(
            summary.overview(name) is not None
            for name in required_overviews
        ) and all(
            isinstance(summary.overview(name).data, dict)
            for name in (
                "environmental_color_histogram",
                "design_color_histogram",
                "colors_distribution",
            )
        ) and isinstance(
            summary.overview("predominant_colors").data,
            tuple,
        )
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return False


CONTRACT = StageContract(
    name="data_processor",
    requires=(
        context_value(K.SESSION, Session),
        context_value(K.PAGE_BUILDER, PageBuilder),
        context_value(K.DOM_TREE, Element),
        context_value(K.COLOR_SCHEME, ColorScheme),
    ),
    produces=(
        context_value(K.COLOR_SCHEME, ColorScheme),
        context_value(K.SUMMARY, Summary, validator=_summary_ready),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has(K.SUMMARY):
        return context

    session = context.get(K.SESSION)
    page_builder = context.get(K.PAGE_BUILDER)
    dom_tree = context.get(K.DOM_TREE)
    color_scheme = context.get(K.COLOR_SCHEME)
    summary = Summary()
    screenshot_path = session.get_path("before.png", "artifacts", "png")

    context.trace.add_stage_event(CONTRACT.name, "start")

    pixel_matrix = image_to_array(screenshot_path)
    excluded_pixels = _process_tree(summary, page_builder, dom_tree)
    environmental_histogram = build_histogram(pixel_matrix)
    design_histogram = build_histogram(
        pixel_matrix,
        excluded_pixels,
    )
    colors_distribution = _colors_distribution(
        color_scheme,
        design_histogram,
    )
    predominant_colors = _predominant_colors(colors_distribution)
    _build_tonal_palettes(color_scheme, predominant_colors)

    summary.add_overview(
        "environmental_color_histogram",
        environmental_histogram,
    )
    summary.add_overview(
        "design_color_histogram",
        design_histogram,
    )
    summary.add_overview(
        "colors_distribution",
        colors_distribution,
    )
    summary.add_overview(
        "predominant_colors",
        predominant_colors,
    )
    render_palette_preview(
        color_scheme.get_palettes(),
        session.get_path("palette_preview.png", "artifacts", "png"),
    )

    context.set(K.COLOR_SCHEME, color_scheme)
    context.set(K.SUMMARY, summary)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "summary_ready": _summary_ready(summary),
            "predominant_color_count": len(predominant_colors),
            "palette_count": len(color_scheme.get_palettes()),
        },
    )
    return context


def _colors_distribution(
    color_scheme: ColorScheme,
    design_histogram: dict[str, int],
) -> dict[Color, float]:
    total = sum(design_histogram.values())
    if total <= 0:
        return {}

    colors_distribution: dict[Color, float] = {}

    for color, count in design_histogram.items():
        closest = color_scheme.find_closest(color, "colors")
        if closest is None:
            continue

        percentage = round((count / total) * 100, 4)
        colors_distribution[closest] = round(
            colors_distribution.get(closest, 0.0) + percentage,
            4,
        )

    return dict(
        sorted(
            colors_distribution.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )


def _predominant_colors(
    colors_distribution: dict[Color, float],
) -> tuple[Color, ...]:
    chromatic_families: list[
        tuple[Color, float, float, float]
    ] = []

    # colors_distribution ya llega ordenado de mayor a menor popularidad.
    for color, percentage in colors_distribution.items():
        try:
            if color.is_achromatic():
                continue

            hue, chroma, _tone = (
                color
                .convert("hct")
                .coords(nans=False)
            )

            hue = float(hue)
            chroma = float(chroma)
            matched_index: int | None = None
            closest_distance = float("inf")

            for index, (
                _seed_color,
                _family_percentage,
                seed_hue,
                seed_chroma,
            ) in enumerate(chromatic_families):
                hue_delta = abs(hue - seed_hue) % 360.0
                hue_delta = min(
                    hue_delta,
                    360.0 - hue_delta,
                )
                chroma_delta = abs(
                    chroma - seed_chroma
                )

                if (
                    hue_delta > _FAMILY_HUE_DELTA_THRESHOLD
                    or chroma_delta > _FAMILY_CHROMA_DELTA_THRESHOLD
                ):
                    continue

                distance = (
                    hue_delta / _FAMILY_HUE_DELTA_THRESHOLD
                    + chroma_delta / _FAMILY_CHROMA_DELTA_THRESHOLD
                )

                if distance < closest_distance:
                    closest_distance = distance
                    matched_index = index

            if matched_index is None:
                chromatic_families.append(
                    (
                        color,
                        float(percentage),
                        hue,
                        chroma,
                    )
                )
                continue

            (
                seed_color,
                family_percentage,
                seed_hue,
                seed_chroma,
            ) = chromatic_families[matched_index]

            chromatic_families[matched_index] = (
                seed_color,
                round(
                    family_percentage + float(percentage),
                    4,
                ),
                seed_hue,
                seed_chroma,
            )
        except Exception:
            continue

    chromatic_families.sort(
        key=lambda family: family[1],
        reverse=True,
    )

    return tuple(
        seed_color
        for (
            seed_color,
            _percentage,
            _hue,
            _chroma,
        ) in chromatic_families[
            :_PREDOMINANT_COLOR_LIMIT
        ]
    )


def _build_tonal_palettes(
    color_scheme: ColorScheme,
    predominant_colors: tuple[Color, ...],
) -> ColorScheme:
    for color_index, color in enumerate(
        predominant_colors,
        start=1,
    ):
        color_scheme.add_palette(
            f"Color {color_index}",
            color,
        )

    return color_scheme


def _process_tree(
    summary: Summary,
    page_builder: PageBuilder,
    root: Element,
) -> list[list[tuple[float, float]]]:
    issue_id = 1
    quads: list[list[tuple[float, float]]] = []

    for element in root.iter_dfs():
        try:
            excluded_pixels = get_html_element_category(element.tag_name) == "media" or element.has_image or get_html_element_category(element.tag_name) == "input"

            if excluded_pixels:
                quad = page_builder.get_box_model(element.backend_node_id)
                if quad:
                    quads.append(quad)

            if not element.has_text or element.node_id is None:
                continue

            background_data = page_builder.get_background_colors(element.node_id)
            contrast = element.get_text_contrast(
                background_colors=background_data.get("background_colors", ()),
                font_size=background_data.get("font_size"),
                font_weight=background_data.get("font_weight"),
            )
            if contrast is None:
                continue

            (
                foreground,
                background,
                contrast_ratio,
                required_ratio,
                is_large_text,
            ) = contrast

            if contrast_ratio >= required_ratio:
                continue

            summary.add_contrast_issue(
                issue_id=issue_id,
                backend_node_id=element.backend_node_id,
                contrast_ratio=contrast_ratio,
                required_ratio=required_ratio,
                is_large_text=is_large_text,
                foreground=foreground.convert("srgb").to_string(hex=True),
                background=background.convert("srgb").to_string(hex=True),
            )
            issue_id += 1
        except Exception:
            continue

    return quads
