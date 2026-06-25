from __future__ import annotations

from typing import Any

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.utils.palette_preview import render_palette_preview
from engine.adapters.utils.pixel import build_histogram, image_to_array
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import Color, ColorScheme
from engine.domain.models.element import Element
from engine.domain.models.session import Session
from engine.domain.models.summary import Summary
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.domain.utils.parsers import is_gradient

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
_FAMILY_COMPARISON_TONE = 60
_FAMILY_HUE_DELTA_THRESHOLD = 12.0
_FAMILY_CHROMA_DELTA_THRESHOLD = 30.0
_FAMILY_NORMALIZED_DELTA_E_THRESHOLD = 10.0
_FAMILY_FALLBACK_DELTA_E_THRESHOLD = 6.0


def _summary_ready(summary: Summary) -> bool:
    try:
        required_overviews = (
            "environmental_color_histogram",
            "design_color_histogram",
            "colors_distribution",
            "predominant_colors",
        )
        return all(summary.overview(name) is not None for name in required_overviews) and all(
            isinstance(summary.overview(name).data, dict)
            for name in (
                "environmental_color_histogram",
                "design_color_histogram",
                "colors_distribution",
            )
        ) and isinstance(summary.overview("predominant_colors").data, tuple)
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
    excluded_quads = _build_contrast_issues(summary, page_builder, dom_tree)
    environmental_histogram = build_histogram(pixel_matrix)
    design_histogram = build_histogram(
        pixel_matrix,
        excluded_quads,
    )
    colors_distribution = _colors_distribution(color_scheme, design_histogram)
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
        percent = round((count / total) * 100, 4)
        colors_distribution[closest] = round(
            colors_distribution.get(closest, 0.0) + percent,
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
    chromatic_families: list[tuple[Color, float]] = []

    for color, _percentage in sorted(
        colors_distribution.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        try:
            if color.is_achromatic():
                continue
        except Exception:
            continue

        percentage = float(_percentage)
        matched_index = next(
            (
                index
                for index, (seed_color, _family_percentage) in enumerate(chromatic_families)
                if _same_chromatic_family(seed_color, color)
            ),
            None,
        )
        if matched_index is None:
            chromatic_families.append((color, percentage))
            continue

        seed_color, family_percentage = chromatic_families[matched_index]
        chromatic_families[matched_index] = (
            seed_color,
            round(family_percentage + percentage, 4),
        )

    chromatic_families.sort(key=lambda item: item[1], reverse=True)
    return tuple(
        color
        for color, _percentage in chromatic_families[:_PREDOMINANT_COLOR_LIMIT]
    )


def _build_tonal_palettes(
    color_scheme: ColorScheme,
    predominant_colors: tuple[Color, ...],
) -> ColorScheme:
    for color_index, color in enumerate(predominant_colors, start=1):
        color_scheme.add_palette(f"Color {color_index}", color)
    return color_scheme


def _same_chromatic_family(seed_color: Color, candidate_color: Color) -> bool:
    try:
        seed_normalized = _comparison_color(seed_color)
        candidate_normalized = _comparison_color(candidate_color)
        seed_hue, seed_chroma, _seed_tone = seed_normalized.convert("hct").coords(nans=False)
        candidate_hue, candidate_chroma, _candidate_tone = candidate_normalized.convert("hct").coords(nans=False)

        if (
            _hue_distance(float(seed_hue), float(candidate_hue)) <= _FAMILY_HUE_DELTA_THRESHOLD
            and abs(float(seed_chroma) - float(candidate_chroma)) <= _FAMILY_CHROMA_DELTA_THRESHOLD
            and seed_normalized.delta_e(candidate_normalized) <= _FAMILY_NORMALIZED_DELTA_E_THRESHOLD
        ):
            return True

        return seed_color.delta_e(candidate_color) <= _FAMILY_FALLBACK_DELTA_E_THRESHOLD
    except Exception:
        return False


def _comparison_color(color: Color) -> Color:
    return (
        color
        .convert("hct")
        .clone()
        .set("tone", _FAMILY_COMPARISON_TONE)
        .fit("srgb", method="raytrace", pspace="hct")
        .convert("srgb")
    )


def _hue_distance(left_hue: float, right_hue: float) -> float:
    distance = abs(left_hue - right_hue) % 360.0
    return min(distance, 360.0 - distance)


def _build_contrast_issues(
    summary: Summary,
    page_builder: PageBuilder,
    root: Element,
) -> list[list[tuple[float, float]]]:
    issue_id = 1
    quads: list[list[tuple[float, float]]] = []
    elements = tuple(root.iter_dfs())

    for element in elements:
        if element.has_tag(*_MEDIA_TAGS) or element.property("background-image") is not None and not is_gradient(element.property("background-image").value):
            try:
                quad = page_builder.get_box_model(element.backend_node_id)
            except RuntimeError:
                continue
            if quad:
                quads.append(quad)
            continue

        if element.tag_name != "#text":
            continue

        container = root.find_by_backend_node_id(element.parent_backend_node_id)
        target_node_id = container.node_id

        foreground = container.property("color").value

        background_data = page_builder.get_background_colors(target_node_id)
        background_colors = background_data.get("background_colors")
        if not background_colors:
            continue

        worst_background = _worst_background(foreground, background_colors)
        if not worst_background:
            continue

        worst_color, lowest_contrast = worst_background
        font_size = _css_number(background_data.get("font_size"))
        font_weight = _css_font_weight(background_data.get("font_weight"))
        is_large_text = font_size >= 18 or (font_size >= 14 and font_weight >= 700)
        required_ratio = 3.1 if is_large_text else 4.5
        if lowest_contrast >= required_ratio:
            continue

        summary.add_contrast_issue(
            issue_id=issue_id,
            backend_node_id=container.backend_node_id,
            contrast_ratio=lowest_contrast,
            required_ratio=required_ratio,
            is_large_text=is_large_text,
            foreground=Color(foreground).convert('srgb').to_string(hex=True),
            background=worst_color.convert('srgb').to_string(hex=True),
        )
        issue_id += 1
    return quads


def _worst_background(foreground: str, backgrounds: list[str]) -> tuple[Any, float] | None:
    """Encuentra el color de fondo con el menor contraste respecto al texto."""
    try:
        fg_color = Color(foreground)
        
        # Creamos una lista de tuplas (objeto_color, valor_contraste)
        candidates = [
            (bg_obj := Color(bg), fg_color.contrast(bg_obj))
            for bg in backgrounds
        ]
        
        if not candidates:
            return None

        # min() compara automáticamente basándose en el segundo elemento de la tupla (el contraste)
        return min(candidates, key=lambda item: item[1])

    except Exception:
        return None


def _css_number(value: object) -> float:
    normalized = str(value or "").strip().lower()
    if normalized.endswith("px"):
        normalized = normalized[:-2]
    try:
        return float(normalized)
    except ValueError:
        return 0.0


def _css_font_weight(value: object) -> int:
    normalized = str(value or "").strip().lower()
    keyword_weights = {
        "normal": 400,
        "bold": 700,
        "lighter": 300,
        "bolder": 700,
        "initial": 400,
        "inherit": 400,
        "unset": 400,
        "revert": 400,
    }
    if normalized in keyword_weights:
        return keyword_weights[normalized]
    try:
        return int(float(normalized))
    except ValueError:
        return 400
