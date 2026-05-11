from __future__ import annotations

from engine.adapters.utils.palette_preview import render_palette_preview
from engine.adapters.utils.pixel import (
    build_color_histograms,
    color_histogram_total,
    get_color_count,
)
from engine.domain.models.color import ColorCatalog
from engine.domain.models.color_scheme import ColorSchemeModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import BEFORE_SCREENSHOT, PALETTE_PREVIEW, Session
from engine.domain.utils.palette_analysis import (
    build_named_color_breakdown,
    build_palette_seed_specs,
    filter_supported_colors,
    map_colors_to_scheme,
)
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_scheme(session: Session) -> bool:
    return bool(session.session_id.strip())

CONTRACT = StageContract(
    name="build_color_scheme",
    requires=(
        context_value(K.PROTOTYPE_STRUCTURE, PrototypeStructure),
        context_value(K.COLOR_CATALOG, ColorCatalog),
        context_value(K.SESSION, Session, validator=_session_ready_for_scheme),
    ),
    produces=(
        context_value(K.COLOR_CATALOG, ColorCatalog),
        context_value(K.ENVIRONMENTAL_BEFORE_COLOR_HISTOGRAM, list),
        context_value(K.SCHEME_COLOR_HISTOGRAM, list),
        context_value(K.SCHEME_TONAL_PALETTES, ColorSchemeModel),
        context_value(K.SCHEME_NAMED_COLOR_BREAKDOWN, tuple),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has(K.SCHEME_TONAL_PALETTES):
        return context

    session = context.get(K.SESSION)
    prototype_structure = context.get(K.PROTOTYPE_STRUCTURE)
    colors_inventory = context.get(K.COLOR_CATALOG)
    context.trace.add_stage_event(CONTRACT.name, "start")
    before_screenshot = session.build_path("artifacts", BEFORE_SCREENSHOT)
    color_histograms = build_color_histograms(
        before_screenshot,
        prototype_structure=prototype_structure,
        cluster_distance=6.0,
    )
    environmental_color_histogram = color_histograms["environmental"]
    scheme_color_histogram = color_histograms["scheme"]
    context.set(K.ENVIRONMENTAL_BEFORE_COLOR_HISTOGRAM, environmental_color_histogram)
    context.set(K.SCHEME_COLOR_HISTOGRAM, scheme_color_histogram)

    total_pixels = color_histogram_total(scheme_color_histogram)
    counts_by_color_id = {}
    for entry in colors_inventory:
        record = get_color_count(scheme_color_histogram, *entry.rgb)
        pixel_count = int(record.get("count") or 0)
        pixel_percentage = round((pixel_count / total_pixels) * 100, 4) if total_pixels else 0.0
        counts_by_color_id[entry.color_id] = (pixel_count, pixel_percentage)
    colors_inventory = colors_inventory.with_pixel_counts(counts_by_color_id)
    context.set(K.COLOR_CATALOG, colors_inventory)
    semantic_colors = filter_supported_colors(colors_inventory if len(colors_inventory) else ())
    achromatic_seed, chromatic_seeds = build_palette_seed_specs(semantic_colors)
    color_scheme_model = ColorSchemeModel.build(
        achromatic_seed=achromatic_seed,
        chromatic_seeds=chromatic_seeds,
    )
    mapped_colors = map_colors_to_scheme(color_scheme_model, semantic_colors)
    mapped_pixel_count = sum(color.pixel_count for color in mapped_colors)
    named_color_breakdown = build_named_color_breakdown(
        mapped_colors,
        total_pixels=mapped_pixel_count,
    )
    preview_path = session.build_path("artifacts", PALETTE_PREVIEW)

    render_palette_preview(color_scheme_model.to_dict(), preview_path)
    colors_inventory = colors_inventory.with_palette_mappings(mapped_colors)
    context.set(K.COLOR_CATALOG, colors_inventory)
    context.set(K.SCHEME_TONAL_PALETTES, color_scheme_model)
    context.set(K.SCHEME_NAMED_COLOR_BREAKDOWN, named_color_breakdown)
    context.trace.add_step(
        "scheme.built",
        {
            "semantic_color_count": len(mapped_colors),
            "chromatic_palette_count": len(color_scheme_model.chromatic_palettes),
            "scheme_color_count": len(scheme_color_histogram),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "semantic_color_count": len(mapped_colors),
            "scheme_color_count": len(scheme_color_histogram),
        },
    )
    return context
