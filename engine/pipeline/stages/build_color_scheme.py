from __future__ import annotations

from engine.adapters.utils.palette_preview import render_palette_preview
from engine.adapters.utils.pixel import (
    build_color_histograms,
    color_histogram_total,
    get_color_count,
)
from engine.domain.data.material_quantization import get_material_quantization_assessment
from engine.domain.models.color import ColorCatalog
from engine.domain.models.palette import CorePalettesModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import Session
from engine.domain.utils.color_scheme import build_color_scheme_artifact
from engine.domain.utils.color_scheme import build_color_scheme_input
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_scheme(session: Session) -> bool:
    return bool(session.palette_preview_path.strip()) and bool(
        session.original_screenshot_path.strip()
    )

CONTRACT = StageContract(
    name="build_color_scheme",
    requires=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("color.catalog", ColorCatalog),
        context_value("session", Session, validator=_session_ready_for_scheme),
    ),
    produces=(
        context_value("environmental.before.color_histogram", list),
        context_value("scheme.color_histogram", list),
        context_value("scheme.colors", tuple),
        context_value("scheme.tonal_palettes", CorePalettesModel),
        context_value("scheme.named_color_breakdown", tuple),
    ),
)


def _apply_color_counts(
    colors_inventory: ColorCatalog,
    color_histogram: list[dict],
) -> ColorCatalog:
    if not len(colors_inventory):
        return colors_inventory

    total_pixels = color_histogram_total(color_histogram)
    enriched_entries = []
    for entry in colors_inventory:
        record = get_color_count(color_histogram, *entry.rgb)
        pixel_count = int(record.get("count") or 0)
        pixel_percentage = round((pixel_count / total_pixels) * 100, 4) if total_pixels else 0.0
        enriched_entries.append(
            entry.set_count(
                pixel_count,
                percentage=pixel_percentage,
            )
        )
    return colors_inventory.with_entries(enriched_entries)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("scheme.colors"):
        return context

    session = context.get("session")
    prototype_structure = context.get("prototype_structure")
    colors_inventory = context.get("color.catalog")
    context.trace.add_stage_event(CONTRACT.name, "start")
    color_histograms = build_color_histograms(
        session.original_screenshot_path,
        prototype_structure=prototype_structure,
        cluster_distance=6.0,
    )
    environmental_color_histogram = color_histograms["environmental"]
    scheme_color_histogram = color_histograms["scheme"]
    context.set("environmental.before.color_histogram", environmental_color_histogram)
    context.set("scheme.color_histogram", scheme_color_histogram)

    colors_inventory = _apply_color_counts(colors_inventory, scheme_color_histogram)
    context.set("color.catalog", colors_inventory)
    scheme_input = build_color_scheme_input(
        colors_inventory if len(colors_inventory) else (),
        material_quantization_assessment=get_material_quantization_assessment(),
    )
    color_scheme_model = build_color_scheme_artifact(scheme_input)
    preview_path = session.palette_preview_path

    render_palette_preview(color_scheme_model.to_dict(), preview_path)
    context.set("scheme.colors", color_scheme_model.semantic_colors)
    context.set("scheme.tonal_palettes", color_scheme_model.core_palettes)
    context.set("scheme.named_color_breakdown", color_scheme_model.named_color_breakdown)
    context.trace.add_step(
        "scheme.built",
        {
            "semantic_color_count": len(color_scheme_model.semantic_colors),
            "chromatic_palette_count": len(color_scheme_model.core_palettes.chromatic_palettes),
            "scheme_color_count": len(scheme_color_histogram),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "semantic_color_count": len(color_scheme_model.semantic_colors),
            "scheme_color_count": len(scheme_color_histogram),
        },
    )
    return context
