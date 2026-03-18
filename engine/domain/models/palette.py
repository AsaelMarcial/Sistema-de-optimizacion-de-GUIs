from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any, Iterator, Sequence

from engine.domain.models.color import SnapshotColorEvidence, ToneStopModel
from engine.domain.utils.colors import (
    color_to_hex,
    color_to_rgb_tuple,
    display_color,
    hct_coords,
    tonal_palette_color,
)

_DEFAULT_ACHROMATIC_TONAL_STOPS: tuple[int, ...] = (
    0,
    10,
    20,
    30,
    40,
    50,
    60,
    70,
    80,
    90,
    95,
    98,
    99,
    100,
)
_DEFAULT_CHROMATIC_TONAL_STOPS: tuple[int, ...] = (10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98)


def _default_tonal_stops(palette_type: str) -> tuple[int, ...]:
    if palette_type == "chromatic":
        return _DEFAULT_CHROMATIC_TONAL_STOPS
    return _DEFAULT_ACHROMATIC_TONAL_STOPS


@dataclass(frozen=True, slots=True)
class TonalPaletteModel:
    palette_id: str
    palette_type: str
    role_bias: str
    seed_name: str | None
    seed_color_id: str | None
    seed_hex: str
    seed_rgb: tuple[int, int, int]
    seed_hct: tuple[float, float, float]
    hue: float
    chroma: float
    semantic_weight: int
    confirmed_pixel_count: int
    display_name: str | None = None
    seed_display_name: str | None = None
    seed_family_name: str | None = None
    source_color_ids: tuple[str, ...] = field(default_factory=tuple)
    tones: tuple[ToneStopModel, ...] = field(default_factory=tuple)

    @classmethod
    def from_seed(
        cls,
        *,
        palette_id: str,
        palette_type: str,
        seed_hex: str,
        role_bias: str,
        semantic_weight: int,
        confirmed_pixel_count: int,
        seed_name: str | None = None,
        seed_color_id: str | None = None,
        source_color_ids: Sequence[str] = (),
        tones: Sequence[int] | None = None,
        chroma_override: float | None = None,
    ) -> "TonalPaletteModel":
        normalized_seed = display_color(seed_hex)
        hue, seed_chroma, _ = hct_coords(normalized_seed)
        chroma = seed_chroma if chroma_override is None else chroma_override
        palette_tones = tuple(int(value) for value in (tones or _default_tonal_stops(palette_type)))
        tone_models = tuple(
            ToneStopModel.from_color(
                int(tone_value),
                tonal_palette_color(normalized_seed, float(tone_value), chroma_override=chroma_override),
            )
            for tone_value in palette_tones
        )
        return cls(
            palette_id=palette_id,
            palette_type=palette_type,
            role_bias=role_bias,
            seed_name=seed_name,
            seed_color_id=seed_color_id,
            seed_hex=color_to_hex(normalized_seed),
            seed_rgb=color_to_rgb_tuple(normalized_seed),
            seed_hct=hct_coords(normalized_seed),  # type: ignore[arg-type]
            hue=round(float(hue), 4),
            chroma=round(float(chroma), 4),
            semantic_weight=semantic_weight,
            confirmed_pixel_count=confirmed_pixel_count,
            source_color_ids=tuple(source_color_ids),
            tones=tone_models,
        )

    def __iter__(self) -> Iterator[ToneStopModel]:
        return iter(self.tones)

    def to_dict(self) -> dict[str, Any]:
        return {
            "palette_id": self.palette_id,
            "palette_type": self.palette_type,
            "seed_name": self.seed_name,
            "seed_color_id": self.seed_color_id,
            "seed_hex": self.seed_hex,
            "seed_rgb": list(self.seed_rgb),
            "seed_hct": list(self.seed_hct),
            "hue": self.hue,
            "chroma": self.chroma,
            "semantic_weight": self.semantic_weight,
            "confirmed_pixel_count": self.confirmed_pixel_count,
            "display_name": self.display_name,
            "seed_display_name": self.seed_display_name,
            "seed_family_name": self.seed_family_name,
            "source_color_ids": list(self.source_color_ids),
            "tones": [tone.to_dict() for tone in self.tones],
        }


@dataclass(frozen=True, slots=True)
class CorePalettesModel:
    achromatic_palette: TonalPaletteModel | None
    chromatic_palettes: tuple[TonalPaletteModel, ...] = field(default_factory=tuple)
    max_chromatic_palettes: int = 12

    def __iter__(self) -> Iterator[TonalPaletteModel]:
        if self.achromatic_palette is not None:
            yield self.achromatic_palette
        yield from self.chromatic_palettes

    def to_dict(self) -> dict[str, Any]:
        return {
            "achromatic_palette": (
                self.achromatic_palette.to_dict() if self.achromatic_palette else None
            ),
            "chromatic_palettes": [palette.to_dict() for palette in self.chromatic_palettes],
            "max_chromatic_palettes": self.max_chromatic_palettes,
            "selected_chromatic_palettes": len(self.chromatic_palettes),
        }


@dataclass(frozen=True, slots=True)
class ContrastCurveModel:
    low: float
    normal: float
    medium: float
    high: float

    def get(self, contrast_level: float) -> float:
        if contrast_level <= -1.0:
            return self.low
        if contrast_level < 0.0:
            return self.low + ((self.normal - self.low) * ((contrast_level + 1.0) / 1.0))
        if contrast_level < 0.5:
            return self.normal + ((self.medium - self.normal) * (contrast_level / 0.5))
        if contrast_level < 1.0:
            return self.medium + ((self.high - self.medium) * ((contrast_level - 0.5) / 0.5))
        return self.high

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


class TonePolarityModel(StrEnum):
    DARKER = "darker"
    LIGHTER = "lighter"
    RELATIVE_DARKER = "relative_darker"
    RELATIVE_LIGHTER = "relative_lighter"


class ToneDeltaConstraintModel(StrEnum):
    EXACT = "exact"
    NEARER = "nearer"
    FARTHER = "farther"


@dataclass(frozen=True, slots=True)
class ToneDeltaPairModel:
    role_a: str
    role_b: str
    delta: float
    polarity: TonePolarityModel
    stay_together: bool = True
    constraint: ToneDeltaConstraintModel = ToneDeltaConstraintModel.EXACT

    def to_dict(self) -> dict[str, Any]:
        return {
            "role_a": self.role_a,
            "role_b": self.role_b,
            "delta": self.delta,
            "polarity": self.polarity.value,
            "stay_together": self.stay_together,
            "constraint": self.constraint.value,
        }


@dataclass(frozen=True, slots=True)
class DynamicSchemeSpecModel:
    scheme_id: str
    source_color_ids: tuple[str, ...]
    primary_palette_id: str | None
    achromatic_palette_id: str | None
    chromatic_palette_ids: tuple[str, ...]
    is_dark: bool = False
    contrast_level: float = 0.0
    contrast_curve: ContrastCurveModel = field(
        default_factory=lambda: ContrastCurveModel(low=3.0, normal=4.5, medium=7.0, high=11.0)
    )
    tone_delta_pairs: tuple[ToneDeltaPairModel, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scheme_id": self.scheme_id,
            "source_color_ids": list(self.source_color_ids),
            "primary_palette_id": self.primary_palette_id,
            "achromatic_palette_id": self.achromatic_palette_id,
            "chromatic_palette_ids": list(self.chromatic_palette_ids),
            "is_dark": self.is_dark,
            "contrast_level": self.contrast_level,
            "contrast_curve": self.contrast_curve.to_dict(),
            "tone_delta_pairs": [pair.to_dict() for pair in self.tone_delta_pairs],
        }


@dataclass(frozen=True, slots=True)
class MaterialQuantizationAssessment:
    recommended: bool
    summary: str
    resize_before_quantization: bool
    recommended_size: tuple[int, int]
    recommended_quantizer: str
    recommended_max_colors: int
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PaletteAnalysisModel:
    semantic_colors: tuple[SnapshotColorEvidence, ...]
    named_color_breakdown: tuple[dict[str, Any], ...]
    core_palettes: CorePalettesModel
    dynamic_scheme: DynamicSchemeSpecModel
    material_quantization_assessment: MaterialQuantizationAssessment
    confirmed_pixel_count: int
    residual_pixel_count: int
    residual_distinct_colors: int

    def __iter__(self) -> Iterator[SnapshotColorEvidence]:
        return iter(self.semantic_colors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_colors": [item.to_dict() for item in self.semantic_colors],
            "named_color_breakdown": [dict(item) for item in self.named_color_breakdown],
            "core_palettes": self.core_palettes.to_dict(),
            "dynamic_scheme": self.dynamic_scheme.to_dict(),
            "material_quantization_assessment": self.material_quantization_assessment.to_dict(),
            "confirmed_pixel_count": self.confirmed_pixel_count,
            "residual_pixel_count": self.residual_pixel_count,
            "residual_distinct_colors": self.residual_distinct_colors,
        }
