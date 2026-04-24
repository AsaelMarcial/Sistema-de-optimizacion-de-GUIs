from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any, Iterator, Sequence, Self

from engine.adapters.color_service import color_registry
from engine.domain.data.web_colors import get_web_color
from engine.domain.enums.types.color import ColorFamilyType, PaletteRoleBias
from engine.domain.models.color import Color

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
_ACHROMATIC_PALETTE_CHROMA = 6.0
_MAX_CHROMATIC_PALETTES = 12


def _coerce_palette_type(value: ColorFamilyType | str) -> ColorFamilyType:
    if isinstance(value, ColorFamilyType):
        return value
    return ColorFamilyType(str(value).strip().lower())


def _coerce_role_bias(value: PaletteRoleBias | str) -> PaletteRoleBias:
    if isinstance(value, PaletteRoleBias):
        return value
    return PaletteRoleBias(str(value).strip().lower())


def _default_tonal_stops(palette_type: ColorFamilyType | str) -> tuple[int, ...]:
    if _coerce_palette_type(palette_type) == ColorFamilyType.CHROMATIC:
        return _DEFAULT_CHROMATIC_TONAL_STOPS
    return _DEFAULT_ACHROMATIC_TONAL_STOPS


def _specific_palette_name(color_name: str | None) -> str | None:
    if not color_name:
        return None
    try:
        return get_web_color(color_name).display_name
    except Exception:
        return color_name.replace("_", " ").title()


def _family_palette_name(
    color_name: str | None,
    *,
    palette_type: ColorFamilyType | str,
) -> str:
    if _coerce_palette_type(palette_type) == ColorFamilyType.ACHROMATIC:
        return "Neutral"
    if not color_name:
        return "Chromatic"
    try:
        return get_web_color(color_name).family_display_name
    except Exception:
        return color_name.replace("_", " ").title()


def _broad_color_family(
    color_name: str | None,
    *,
    palette_type: ColorFamilyType | str,
) -> str | None:
    if _coerce_palette_type(palette_type) == ColorFamilyType.ACHROMATIC:
        return "Neutral"
    if not color_name:
        return None
    try:
        return get_web_color(color_name).wikipedia_family
    except Exception:
        return None


@dataclass(frozen=True, slots=True)
class ToneStopModel:
    tone: int
    hex_value: str
    rgb: tuple[int, int, int]
    hct: tuple[float, float, float]

    @classmethod
    def from_color(cls, tone: int, color_value: Any) -> Self:
        normalized = color_registry.display_color(color_value)
        return cls(
            tone=tone,
            hex_value=color_registry.format_color(normalized, "hex"),
            rgb=color_registry.format_color(normalized, "rgb"),
            hct=color_registry.hct_of(normalized),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tone": self.tone,
            "hex_value": self.hex_value,
            "rgb": list(self.rgb),
            "hct": list(self.hct),
        }


@dataclass(frozen=True, slots=True)
class PaletteFamilyModel:
    palette_type: ColorFamilyType
    seed_color_id: str | None
    seed_hex: str
    seed_name: str | None
    seed_family_name: str | None
    comparison_rgb: tuple[int, int, int]
    comparison_hct: tuple[float, float, float]
    semantic_weight: int
    pixel_count: int
    foreground_count: int
    background_count: int
    other_count: int
    source_color_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "palette_type", _coerce_palette_type(self.palette_type))

    def role_bias(self) -> PaletteRoleBias:
        if self.background_count > self.foreground_count and self.background_count >= self.other_count:
            return PaletteRoleBias.BACKGROUND
        if self.foreground_count > self.background_count and self.foreground_count >= self.other_count:
            return PaletteRoleBias.FOREGROUND
        if self.other_count > max(self.background_count, self.foreground_count):
            return PaletteRoleBias.OTHER
        return PaletteRoleBias.MIXED

    def to_dict(self) -> dict[str, Any]:
        return {
            "palette_type": self.palette_type.value,
            "seed_color_id": self.seed_color_id,
            "seed_hex": self.seed_hex,
            "seed_name": self.seed_name,
            "seed_family_name": self.seed_family_name,
            "comparison_rgb": list(self.comparison_rgb),
            "comparison_hct": list(self.comparison_hct),
            "semantic_weight": self.semantic_weight,
            "pixel_count": self.pixel_count,
            "foreground_count": self.foreground_count,
            "background_count": self.background_count,
            "other_count": self.other_count,
            "source_color_ids": list(self.source_color_ids),
        }


@dataclass(frozen=True, slots=True)
class TonalPaletteModel:
    palette_id: str
    palette_type: ColorFamilyType
    role_bias: PaletteRoleBias
    seed_name: str | None
    seed_color_id: str | None
    seed_hex: str
    seed_rgb: tuple[int, int, int]
    seed_hct: tuple[float, float, float]
    hue: float
    chroma: float
    semantic_weight: int
    pixel_count: int
    display_name: str | None = None
    seed_display_name: str | None = None
    seed_family_name: str | None = None
    source_color_ids: tuple[str, ...] = field(default_factory=tuple)
    tones: tuple[ToneStopModel, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "palette_type", _coerce_palette_type(self.palette_type))
        object.__setattr__(self, "role_bias", _coerce_role_bias(self.role_bias))

    @classmethod
    def from_seed(
        cls,
        *,
        palette_id: str,
        palette_type: ColorFamilyType | str,
        seed_hex: str,
        role_bias: PaletteRoleBias | str,
        semantic_weight: int,
        pixel_count: int,
        seed_name: str | None = None,
        seed_color_id: str | None = None,
        source_color_ids: Sequence[str] = (),
        tones: Sequence[int] | None = None,
        chroma_override: float | None = None,
    ) -> Self:
        normalized_seed = color_registry.display_color(seed_hex)
        hue, seed_chroma, _ = color_registry.hct_of(normalized_seed)
        chroma = seed_chroma if chroma_override is None else chroma_override
        palette_tones = tuple(int(value) for value in (tones or _default_tonal_stops(palette_type)))
        tone_models = tuple(
            ToneStopModel.from_color(
                int(tone_value),
                color_registry.tonal_color(
                    normalized_seed,
                    float(tone_value),
                    chroma_override=chroma_override,
                ),
            )
            for tone_value in palette_tones
        )
        return cls(
            palette_id=palette_id,
            palette_type=palette_type,
            role_bias=role_bias,
            seed_name=seed_name,
            seed_color_id=seed_color_id,
            seed_hex=color_registry.format_color(normalized_seed, "hex"),
            seed_rgb=color_registry.format_color(normalized_seed, "rgb"),
            seed_hct=color_registry.hct_of(normalized_seed),  # type: ignore[arg-type]
            hue=round(float(hue), 4),
            chroma=round(float(chroma), 4),
            semantic_weight=semantic_weight,
            pixel_count=pixel_count,
            source_color_ids=tuple(source_color_ids),
            tones=tone_models,
        )

    @classmethod
    def from_family(cls, family: PaletteFamilyModel, *, palette_index: int) -> Self:
        return cls.from_seed(
            palette_id=f"palette-{family.palette_type}-{palette_index}",
            palette_type=family.palette_type,
            seed_hex=family.seed_hex,
            role_bias=family.role_bias(),
            semantic_weight=family.semantic_weight,
            pixel_count=family.pixel_count,
            seed_name=family.seed_name,
            seed_color_id=family.seed_color_id,
            source_color_ids=tuple(family.source_color_ids),
            chroma_override=(
                _ACHROMATIC_PALETTE_CHROMA if family.palette_type == "achromatic" else None
            ),
        )

    def __iter__(self) -> Iterator[ToneStopModel]:
        return iter(self.tones)

    def nearest_tone_to(self, rgb: tuple[int, int, int]) -> tuple[ToneStopModel | None, float | None]:
        best_tone: ToneStopModel | None = None
        best_distance: float | None = None
        for tone_stop in self.tones:
            distance = color_registry.delta_e_distance(rgb, tone_stop.rgb, method="2000")
            if best_distance is None or distance < best_distance:
                best_tone = tone_stop
                best_distance = distance
        return best_tone, best_distance

    def to_dict(self) -> dict[str, Any]:
        return {
            "palette_id": self.palette_id,
            "palette_type": self.palette_type.value,
            "seed_name": self.seed_name,
            "seed_color_id": self.seed_color_id,
            "seed_hex": self.seed_hex,
            "seed_rgb": list(self.seed_rgb),
            "seed_hct": list(self.seed_hct),
            "hue": self.hue,
            "chroma": self.chroma,
            "semantic_weight": self.semantic_weight,
            "pixel_count": self.pixel_count,
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
    max_chromatic_palettes: int = _MAX_CHROMATIC_PALETTES

    @classmethod
    def build(
        cls,
        *,
        achromatic_family: PaletteFamilyModel | None,
        chromatic_families: Sequence[PaletteFamilyModel] = (),
        max_chromatic_palettes: int = _MAX_CHROMATIC_PALETTES,
    ) -> Self:
        achromatic_palette = (
            TonalPaletteModel.from_family(achromatic_family, palette_index=1)
            if achromatic_family is not None
            else cls._fallback_achromatic_palette()
        )
        chromatic_palettes = tuple(
            TonalPaletteModel.from_family(family, palette_index=index)
            for index, family in enumerate(chromatic_families[:max_chromatic_palettes], start=1)
        )
        return cls._annotate_names(
            cls(
                achromatic_palette=achromatic_palette,
                chromatic_palettes=chromatic_palettes,
                max_chromatic_palettes=max_chromatic_palettes,
            )
        )

    @staticmethod
    def _fallback_achromatic_palette() -> TonalPaletteModel:
        return TonalPaletteModel.from_seed(
            palette_id="palette-achromatic-1",
            palette_type="achromatic",
            seed_hex="#ffffff",
            role_bias="background",
            semantic_weight=0,
            pixel_count=0,
            seed_name="white",
            source_color_ids=(),
            chroma_override=_ACHROMATIC_PALETTE_CHROMA,
        )

    @classmethod
    def _annotate_names(cls, core_palettes: Self) -> Self:
        achromatic_palette = core_palettes.achromatic_palette
        if achromatic_palette is not None:
            achromatic_palette = replace(
                achromatic_palette,
                display_name="Neutral",
                seed_display_name=_specific_palette_name(achromatic_palette.seed_name),
                seed_family_name="Neutral",
            )

        family_names = [
            _family_palette_name(palette.seed_name, palette_type=palette.palette_type)
            for palette in core_palettes.chromatic_palettes
        ]
        family_counts = Counter(family_names)
        named_chromatic_palettes: list[TonalPaletteModel] = []
        for palette, family_name in zip(core_palettes.chromatic_palettes, family_names):
            specific_name = _specific_palette_name(palette.seed_name)
            display_name = family_name if family_counts[family_name] <= 1 else (specific_name or family_name)
            named_chromatic_palettes.append(
                replace(
                    palette,
                    display_name=display_name,
                    seed_display_name=specific_name,
                    seed_family_name=family_name,
                )
            )

        return cls(
            achromatic_palette=achromatic_palette,
            chromatic_palettes=tuple(named_chromatic_palettes),
            max_chromatic_palettes=core_palettes.max_chromatic_palettes,
        )

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
class ColorSchemeModel:
    core_palettes: CorePalettesModel
    dynamic_scheme: DynamicSchemeSpecModel

    @property
    def palette_ids(self) -> tuple[str, ...]:
        return tuple(palette.palette_id for palette in self.core_palettes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "core_palettes": self.core_palettes.to_dict(),
            "dynamic_scheme": self.dynamic_scheme.to_dict(),
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
class ColorSchemeInputModel:
    semantic_colors: tuple[Color, ...]
    named_color_breakdown: tuple[dict[str, Any], ...]
    achromatic_family: PaletteFamilyModel | None
    chromatic_families: tuple[PaletteFamilyModel, ...]
    material_quantization_assessment: MaterialQuantizationAssessment

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_colors": [item.to_dict() for item in self.semantic_colors],
            "named_color_breakdown": [dict(item) for item in self.named_color_breakdown],
            "achromatic_family": (
                self.achromatic_family.to_dict() if self.achromatic_family is not None else None
            ),
            "chromatic_families": [item.to_dict() for item in self.chromatic_families],
            "material_quantization_assessment": self.material_quantization_assessment.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class PaletteAnalysisModel:
    semantic_colors: tuple[Color, ...]
    named_color_breakdown: tuple[dict[str, Any], ...]
    core_palettes: CorePalettesModel
    dynamic_scheme: DynamicSchemeSpecModel
    material_quantization_assessment: MaterialQuantizationAssessment

    @classmethod
    def build_from_components(
        cls,
        *,
        semantic_colors: Sequence[Color],
        named_color_breakdown: Sequence[dict[str, Any]],
        core_palettes: CorePalettesModel,
        dynamic_scheme: DynamicSchemeSpecModel,
        material_quantization_assessment: MaterialQuantizationAssessment,
    ) -> Self:
        return cls(
            semantic_colors=tuple(semantic_colors),
            named_color_breakdown=tuple(dict(item) for item in named_color_breakdown),
            core_palettes=core_palettes,
            dynamic_scheme=dynamic_scheme,
            material_quantization_assessment=material_quantization_assessment,
        )

    def __iter__(self) -> Iterator[Color]:
        return iter(self.semantic_colors)

    @property
    def color_scheme(self) -> ColorSchemeModel:
        return ColorSchemeModel(
            core_palettes=self.core_palettes,
            dynamic_scheme=self.dynamic_scheme,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_colors": [item.to_dict() for item in self.semantic_colors],
            "named_color_breakdown": [dict(item) for item in self.named_color_breakdown],
            "core_palettes": self.core_palettes.to_dict(),
            "dynamic_scheme": self.dynamic_scheme.to_dict(),
            "material_quantization_assessment": self.material_quantization_assessment.to_dict(),
        }


ColorSchemeArtifactModel = PaletteAnalysisModel
