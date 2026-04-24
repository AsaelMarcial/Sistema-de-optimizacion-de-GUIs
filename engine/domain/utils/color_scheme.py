from __future__ import annotations

from typing import Any, Iterable, Mapping

from engine.domain.models.color import Color
from engine.domain.models.palette import (
    ColorSchemeArtifactModel,
    ColorSchemeInputModel,
    CorePalettesModel,
    MaterialQuantizationAssessment,
)
from engine.domain.utils.palette_analysis import (
    _MAX_CHROMATIC_PALETTES,
    _build_dynamic_scheme,
    _build_families,
    _build_named_color_breakdown,
    _filter_supported_evidences,
    _map_evidences,
)


def build_color_scheme_input(
    snapshot_palette: Iterable[Mapping[str, Any] | Color],
    *,
    material_quantization_assessment: MaterialQuantizationAssessment,
    max_chromatic_palettes: int = _MAX_CHROMATIC_PALETTES,
) -> ColorSchemeInputModel:
    del max_chromatic_palettes
    semantic_colors = _filter_supported_evidences(
        Color.build_many(snapshot_palette)
    )
    achromatic_family, chromatic_families = _build_families(semantic_colors)
    pixel_count = sum(item.pixel_count for item in semantic_colors)
    return ColorSchemeInputModel(
        semantic_colors=semantic_colors,
        named_color_breakdown=_build_named_color_breakdown(
            semantic_colors,
            total_pixels=pixel_count,
        ),
        achromatic_family=achromatic_family,
        chromatic_families=chromatic_families,
        material_quantization_assessment=material_quantization_assessment,
    )


def build_color_scheme_artifact(
    scheme_input: ColorSchemeInputModel,
    *,
    max_chromatic_palettes: int = _MAX_CHROMATIC_PALETTES,
) -> ColorSchemeArtifactModel:
    core_palettes = CorePalettesModel.build(
        achromatic_family=scheme_input.achromatic_family,
        chromatic_families=scheme_input.chromatic_families,
        max_chromatic_palettes=max_chromatic_palettes,
    )
    mapped_evidences = _map_evidences(core_palettes, scheme_input.semantic_colors)
    return ColorSchemeArtifactModel.build_from_components(
        semantic_colors=mapped_evidences,
        named_color_breakdown=scheme_input.named_color_breakdown,
        core_palettes=core_palettes,
        dynamic_scheme=_build_dynamic_scheme(core_palettes, mapped_evidences),
        material_quantization_assessment=scheme_input.material_quantization_assessment,
    )
