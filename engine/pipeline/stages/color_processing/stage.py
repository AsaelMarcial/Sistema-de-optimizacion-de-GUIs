from __future__ import annotations

from engine.models.pipeline_context import PipelineContext
from engine.services.color_processing.material_quantization_service import (
    get_material_quantization_assessment,
)
from engine.services.color_processing.pixel_frequency_service import (
    pixels_to_color_frequency,
    pixels_to_color_statistics,
)


def run_color_processing_stage(context: PipelineContext) -> None:
    if context.error or context.color_processing_input is None:
        return

    context.pixel_color_frequencies = pixels_to_color_frequency(context.color_processing_input)
    context.pixel_color_statistics = pixels_to_color_statistics(context.color_processing_input)
    context.trace.add_step(
        "color_processing.completed",
        {
            "frequency_count": len(context.pixel_color_frequencies),
            "statistics_count": len(context.pixel_color_statistics),
            "quantizer": get_material_quantization_assessment().to_dict().get(
                "recommended_quantizer"
            ),
        },
    )
