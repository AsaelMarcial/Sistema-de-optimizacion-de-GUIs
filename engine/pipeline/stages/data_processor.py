from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.utils.pixel import build_histogram, image_to_array
from engine.domain.models.color_scheme import Color, ColorScheme
from engine.domain.models.element import Element
from engine.domain.models.session import Session
from engine.domain.models.summary import Summary
from engine.domain.data.web_colors import nearest_web_color
from engine.domain.utils.css_generator import generate_root_css
from engine.pipeline.context import PipelineContext
from engine.pipeline.glow_runtime import (
    glow_flow,
    glow_task,
)
from prefect.states import Completed, Failed, State, get_state_exception

_PREDOMINANT_COLOR_LIMIT = 13
_HUE_BUCKET_SIZE = 30
_HSL_DISTANCE_THRESHOLD = 40


@glow_task
def _summary_ready(summary: Summary | None) -> State:
    if summary is None:
        raise get_state_exception(Failed(message="No se genero Summary."))

    required_overviews = (
        "environmental_color_histogram",
        "design_color_histogram",
        "colors_distribution",
        "predominant_colors",
    )
    if all(
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
    ):
        return Completed(message="Summary esta listo.")
    raise get_state_exception(Failed(message="Summary no paso validacion."))


@glow_flow
def data_processor(context: PipelineContext):
    session = context.session
    page_builder = context.page_builder
    dom_tree = context.dom_tree
    color_scheme = context.color_scheme
    summary = context.summary
    screenshot_path = session.get_path("before.png", "artifacts", "png")

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
    token_inventory = context.token_inventory
    css_path = _theme_css_path(session)
    css_path.write_text(
        generate_root_css(color_scheme.palettes),
        encoding="utf-8",
    )
    session.save_in_before(css_path)

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

    print({
        "data_processor.complete": {
            "summary_ready": True,
            "predominant_color_count": len(predominant_colors),
            "palette_count": len(color_scheme.get_palettes()),
            "glow_css_path": str(css_path),
        }
    })
    _summary_ready(summary)


def _theme_css_path(session: Session):
    html_file = session.find_by_suffix("before", "html")[0]
    return html_file.parent / "glow.css"


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

    merged_distribution: dict[Color, float] = {}

    for color, percentage in sorted(
        colors_distribution.items(),
        key=lambda item: item[1],
        reverse=True,
    ):
        winner = next(
            (
                existing_color
                for existing_color in merged_distribution
                if color.delta_e(existing_color, method="2000") <= 12
            ),
            None,
        )

        if winner is None:
            merged_distribution[color] = percentage
            continue

        merged_distribution[winner] = round(
            merged_distribution[winner] + percentage,
            4,
        )
    
    return dict(
        sorted(
            merged_distribution.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )


def _predominant_colors(
    colors_distribution: dict[Color, float],
) -> tuple[Color, ...]:
    hue_buckets: dict[int, tuple[Color, float, float]] = {}

    # colors_distribution ya llega ordenado de mayor a menor popularidad.
    for color, percentage in colors_distribution.items():
        try:
            if color.is_achromatic():
                continue

            hue, _saturation, _lightness = (
                color
                .convert("hsl")
                .coords(nans=False)
            )

            hue = float(hue)
            hue_bucket = (
                int(hue // _HUE_BUCKET_SIZE)
                * _HUE_BUCKET_SIZE
            ) % 360
            percentage = float(percentage)

            if hue_bucket not in hue_buckets:
                hue_buckets[hue_bucket] = (
                    color,
                    percentage,
                    percentage,
                )
                continue

            (
                seed_color,
                seed_percentage,
                bucket_percentage,
            ) = hue_buckets[hue_bucket]

            if percentage > seed_percentage:
                seed_color = color
                seed_percentage = percentage

            hue_buckets[hue_bucket] = (
                seed_color,
                seed_percentage,
                round(
                    bucket_percentage + percentage,
                    4,
                ),
            )
        except Exception:
            continue

    hsl_groups: list[tuple[Color, float, float]] = []

    for color, seed_percentage, bucket_percentage in hue_buckets.values():
        try:
            normalized_color = color.convert("hsl").clone()
            normalized_color["l"] = 0.5

            matched_index: int | None = None
            for index, (
                group_color,
                _group_seed_percentage,
                _group_percentage,
            ) in enumerate(hsl_groups):
                normalized_group_color = group_color.convert("hsl").clone()
                normalized_group_color["l"] = 0.5

                if (
                    normalized_color.distance(
                        normalized_group_color,
                        space="hsl",
                    )
                    * 100
                    <= _HSL_DISTANCE_THRESHOLD
                ):
                    matched_index = index
                    break

            if matched_index is None:
                hsl_groups.append(
                    (
                        color,
                        seed_percentage,
                        bucket_percentage,
                    )
                )
                continue

            (
                group_color,
                group_seed_percentage,
                group_percentage,
            ) = hsl_groups[matched_index]

            if seed_percentage > group_seed_percentage:
                group_color = color
                group_seed_percentage = seed_percentage

            hsl_groups[matched_index] = (
                group_color,
                group_seed_percentage,
                round(group_percentage + bucket_percentage, 4),
            )
        except Exception:
            continue

    predominant_groups = sorted(
        hsl_groups,
        key=lambda bucket: bucket[2],
        reverse=True,
    )

    return tuple(
        seed_color
        for (
            seed_color,
            _seed_percentage,
            _bucket_percentage,
        ) in predominant_groups[
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
        name = nearest_web_color(color)
        color_scheme.add_palette(
            name,
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
            excluded_pixels = element.category == "media" or element.has_image or element.category == "input"

            if excluded_pixels:
                quad = page_builder.get_box_model(element.backend_node_id)
                if quad:
                    quads.append(quad)

            if not element.has_text or element.node_id is None:
                continue

            background_data = page_builder.get_background_colors(element.node_id)
            background_colors = background_data.get("background_colors") or ()
            if not background_colors:
                summary.add_warning(
                    warning_id=element.backend_node_id,
                    code="background_colors_unavailable",
                    message="No se pudo obtener el color de fondo para calcular contraste.",
                    backend_node_id=element.backend_node_id,
                    node_id=element.node_id,
                )
                continue

            actual_color = None
            current_property_value = getattr(page_builder, "current_property_value", None)
            if callable(current_property_value):
                actual_color = current_property_value(element.node_id, "color")
            if not actual_color:
                actual_color = page_builder.get_computed_styles_for_node(
                    element.node_id
                ).get("color")
            if not actual_color:
                continue

            contrast = element.get_text_contrast(
                actual_color,
                background_colors=background_colors,
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
                foreground=Color(foreground).convert("srgb").to_string(hex=True),
                background=background.convert("srgb").to_string(hex=True),
            )
            issue_id += 1
        except Exception:
            continue

    return quads
