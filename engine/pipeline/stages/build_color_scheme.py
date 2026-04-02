from __future__ import annotations

from engine.adapters.utils.palette_preview import render_palette_preview
from engine.domain.data.material_quantization import get_material_quantization_assessment
from engine.domain.models.color import ColorInventoryModel, DisplayPixelFrequenciesModel
from engine.domain.models.palette import CorePalettesModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import Session
from engine.domain.utils.color_scheme import build_color_scheme_artifact
from engine.domain.utils.color_scheme import build_color_scheme_input
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_scheme(session: Session) -> bool:
    return session.original_css_overview is not None and bool(session.palette_preview_path.strip())

CONTRACT = StageContract(
    name="build_color_scheme",
    requires=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("scheme.display_pixels", DisplayPixelFrequenciesModel),
        context_value("session", Session, validator=_session_ready_for_scheme),
    ),
    produces=(
        context_value("scheme.colors", tuple),
        context_value("scheme.tonal_palettes", CorePalettesModel),
        context_value("scheme.named_color_breakdown", tuple),
        context_value("scheme.confirmed_pixel_count", int),
        context_value("scheme.residual_pixel_count", int),
        context_value("scheme.residual_distinct_colors", int),
    ),
)


def _apply_display_evidence(
    colors_inventory: ColorInventoryModel,
    display_frequencies: DisplayPixelFrequenciesModel,
) -> ColorInventoryModel:
    if not len(colors_inventory):
        return colors_inventory

    display_by_color_id = {
        record.color_id: record
        for record in display_frequencies
        if record.color_id is not None
    }
    if not display_by_color_id:
        return colors_inventory

    total_pixels = display_frequencies.total_pixels_considered
    enriched_entries = []
    for entry in colors_inventory:
        record = display_by_color_id.get(entry.color_id)
        if record is None:
            enriched_entries.append(entry)
            continue
        pixel_percentage = (
            record.percentage
            if record.percentage is not None
            else (round((record.count / total_pixels) * 100, 4) if total_pixels else 0.0)
        )
        enriched_entries.append(
            entry.with_display_evidence(
                pixel_count=record.count,
                pixel_percentage=pixel_percentage,
                clustered=bool((record.metadata or {}).get("clustered")),
            )
        )
    return colors_inventory.with_entries(enriched_entries)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("scheme.colors"):
        return context

    session = context.get("session")
    prototype_structure = context.get("prototype_structure")
    display_frequencies = context.get("scheme.display_pixels")
    colors_inventory = prototype_structure.build_color_inventory(
        css_overview=session.original_css_overview,
    )
    colors_inventory = _apply_display_evidence(colors_inventory, display_frequencies)
    scheme_input = build_color_scheme_input(
        colors_inventory if len(colors_inventory) else (),
        display_frequencies,
        material_quantization_assessment=get_material_quantization_assessment(),
    )
    context.trace.add_stage_event(CONTRACT.name, "start")
    color_scheme_model = build_color_scheme_artifact(scheme_input)
    preview_path = session.palette_preview_path

    render_palette_preview(color_scheme_model.to_dict(), preview_path)
    context.set("scheme.colors", color_scheme_model.semantic_colors)
    context.set("scheme.tonal_palettes", color_scheme_model.core_palettes)
    context.set("scheme.named_color_breakdown", color_scheme_model.named_color_breakdown)
    context.set("scheme.confirmed_pixel_count", color_scheme_model.confirmed_pixel_count)
    context.set("scheme.residual_pixel_count", color_scheme_model.residual_pixel_count)
    context.set("scheme.residual_distinct_colors", color_scheme_model.residual_distinct_colors)
    context.trace.add_step(
        "scheme.built",
        {
            "semantic_color_count": len(color_scheme_model.semantic_colors),
            "chromatic_palette_count": len(color_scheme_model.core_palettes.chromatic_palettes),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "semantic_color_count": len(color_scheme_model.semantic_colors),
            "confirmed_pixel_count": color_scheme_model.confirmed_pixel_count,
        },
    )
    return context
