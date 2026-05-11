from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence, Self

from engine.domain.data.material_quantization import MaterialQuantizationAssessment
from engine.domain.models.color import Color
from engine.domain.models.color_scheme import ColorSchemeModel, ToneStopModel, TonalPaletteModel


CorePalettesModel = ColorSchemeModel


@dataclass(frozen=True, slots=True)
class ColorSchemeInputModel:
    semantic_colors: tuple[Color, ...] = field(default_factory=tuple)
    named_color_breakdown: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    achromatic_seed: Mapping[str, Any] | None = None
    chromatic_seeds: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    material_quantization_assessment: MaterialQuantizationAssessment | None = None
    max_chromatic_palettes: int = 12


@dataclass(frozen=True, slots=True)
class ColorSchemeArtifactModel:
    semantic_colors: tuple[Color, ...] = field(default_factory=tuple)
    named_color_breakdown: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    core_palettes: CorePalettesModel = field(default_factory=CorePalettesModel)
    dynamic_scheme: Mapping[str, Any] = field(default_factory=dict)
    material_quantization_assessment: MaterialQuantizationAssessment | None = None

    @classmethod
    def build_from_components(
        cls,
        *,
        semantic_colors: Sequence[Color],
        named_color_breakdown: Sequence[Mapping[str, Any]],
        core_palettes: CorePalettesModel,
        dynamic_scheme: Mapping[str, Any] | None = None,
        material_quantization_assessment: MaterialQuantizationAssessment | None = None,
    ) -> Self:
        return cls(
            semantic_colors=tuple(semantic_colors),
            named_color_breakdown=tuple(dict(item) for item in named_color_breakdown),
            core_palettes=core_palettes,
            dynamic_scheme=dict(dynamic_scheme or {}),
            material_quantization_assessment=material_quantization_assessment,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "semantic_colors": [color.to_dict() for color in self.semantic_colors],
            "named_color_breakdown": [dict(item) for item in self.named_color_breakdown],
            "core_palettes": self.core_palettes.to_dict(),
            "dynamic_scheme": dict(self.dynamic_scheme),
        }
        if self.material_quantization_assessment is not None:
            payload["material_quantization_assessment"] = (
                self.material_quantization_assessment.to_dict()
                if hasattr(self.material_quantization_assessment, "to_dict")
                else dict(self.material_quantization_assessment)
            )
        return payload


__all__ = (
    "ColorSchemeArtifactModel",
    "ColorSchemeInputModel",
    "ColorSchemeModel",
    "CorePalettesModel",
    "MaterialQuantizationAssessment",
    "ToneStopModel",
    "TonalPaletteModel",
)
