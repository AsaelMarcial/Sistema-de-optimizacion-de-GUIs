from __future__ import annotations

from engine.pipeline.context import PipelineContext
from engine.services.color_processing.material_quantization_service import (
    get_material_quantization_assessment,
)
from engine.services.color_processing.palette_analysis_service import build_palette_analysis
from engine.services.color_processing.palette_preview_service import render_palette_preview
from engine.services.color_processing.pixel_frequency_service import (
    color_frequency_to_statistics,
    pixels_to_color_frequency,
)
from engine.utils.file_utils import save_json


def run_color_processing_stage(context: PipelineContext) -> None:
    if context.error or context.original_artifacts is None:
        return

    material_quantization_assessment = get_material_quantization_assessment()
    pixel_frequencies = context.original_artifacts.color_frequencies
    if pixel_frequencies is None and context.color_processing_input is not None:
        pixel_frequencies = pixels_to_color_frequency(context.color_processing_input)

    context.pixel_color_frequencies = list(pixel_frequencies or [])
    context.pixel_color_statistics = color_frequency_to_statistics(context.pixel_color_frequencies)
    palette_analysis = build_palette_analysis(
        context.original_artifacts.snapshot.palette,
        context.pixel_color_frequencies,
        material_quantization_assessment=material_quantization_assessment,
    ).to_dict()
    context.palette_analysis = palette_analysis

    if context.palette_analysis_output_path and context.palette_analysis is not None:
        save_json(context.palette_analysis_output_path, context.palette_analysis, indent=4)
    if context.palette_preview_output_path and context.palette_analysis is not None:
        render_palette_preview(context.palette_analysis, context.palette_preview_output_path)

    context.trace.add_step(
        "color_processing.completed",
        {
            "frequency_count": len(context.pixel_color_frequencies),
            "statistics_count": len(context.pixel_color_statistics),
            "semantic_color_count": len(context.palette_analysis.get("semantic_colors", []))
            if context.palette_analysis
            else 0,
            "named_color_count": len(context.palette_analysis.get("named_color_breakdown", []))
            if context.palette_analysis
            else 0,
            "palette_preview_output": context.palette_preview_rel,
            "quantizer": material_quantization_assessment.to_dict().get("recommended_quantizer"),
        },
    )
