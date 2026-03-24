from __future__ import annotations

from engine.domain.data.material_quantization import get_material_quantization_assessment
from engine.domain.models.color import ColorInventoryModel, DisplayPixelFrequenciesModel
from engine.domain.models.palette import ColorSchemeInputModel
from engine.domain.utils.color_scheme import build_color_scheme_input
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="analyze_color_inventory",
    requires=(
        context_value("color.inventory", ColorInventoryModel),
        context_value("session.artifacts.original.pixel_frequencies_display", DisplayPixelFrequenciesModel),
    ),
    produces=(context_value("scheme.input", ColorSchemeInputModel),),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("scheme.input"):
        return context

    colors_inventory = context.get("color.inventory")
    display_frequencies = context.get("session.artifacts.original.pixel_frequencies_display")
    context.trace.add_stage_event(CONTRACT.name, "start")
    scheme_input = build_color_scheme_input(
        colors_inventory if len(colors_inventory) else (),
        display_frequencies,
        material_quantization_assessment=get_material_quantization_assessment(),
    )
    context.set("scheme.input", scheme_input)
    context.trace.add_step(
        "scheme.input_built",
        {
            "semantic_color_count": len(scheme_input.semantic_colors),
            "confirmed_pixel_count": scheme_input.confirmed_pixel_count,
            "residual_pixel_count": scheme_input.residual_pixel_count,
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "semantic_color_count": len(scheme_input.semantic_colors),
            "chromatic_family_count": len(scheme_input.chromatic_families),
        },
    )
    return context
