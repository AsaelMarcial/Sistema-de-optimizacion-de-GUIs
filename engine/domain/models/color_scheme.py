from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Any, Iterator, Mapping, Sequence, Self

from engine.adapters.color_service import color_registry
from engine.domain.data.web_colors import get_web_color
from engine.domain.enums.types.color import ColorFamilyType, PaletteRoleBias

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
_MAX_PALETTES = 12


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


@dataclass(frozen=True, slots=True)
class ToneStopModel:
    tone: int
    hex_value: str
    rgb: tuple[int, int, int]
    hct: tuple[float, float, float]
    token: str | None = None

    @classmethod
    def from_color(cls, tone: int, color_value: Any, *, token: str | None = None) -> Self:
        normalized = color_registry.display_color(color_value)
        return cls(
            tone=tone,
            hex_value=color_registry.format_color(normalized, "hex"),
            rgb=color_registry.format_color(normalized, "rgb"),
            hct=color_registry.hct_of(normalized),  # type: ignore[arg-type]
            token=token,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tone": self.tone,
            "hex_value": self.hex_value,
            "rgb": list(self.rgb),
            "hct": list(self.hct),
        }
        if self.token is not None:
            payload["token"] = self.token
        return payload


@dataclass(frozen=True, slots=True)
class TonalPaletteModel:
    palette_id: str
    palette_type: ColorFamilyType
    role_bias: PaletteRoleBias
    seed_hex: str
    seed_name: str | None = None
    seed_color_id: str | None = None
    display_name: str | None = None
    seed_display_name: str | None = None
    seed_family_name: str | None = None
    tones: tuple[ToneStopModel, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "palette_type", _coerce_palette_type(self.palette_type))
        object.__setattr__(self, "role_bias", _coerce_role_bias(self.role_bias))
        object.__setattr__(
            self,
            "seed_hex",
            color_registry.format_color(color_registry.display_color(self.seed_hex), "hex"),
        )

    @classmethod
    def from_seed(
        cls,
        *,
        palette_id: str,
        palette_type: ColorFamilyType | str,
        seed_hex: str,
        role_bias: PaletteRoleBias | str,
        seed_name: str | None = None,
        seed_color_id: str | None = None,
        tones: Sequence[int] | None = None,
        chroma_override: float | None = None,
        semantic_weight: int | None = None,
        pixel_count: int | None = None,
        source_color_ids: Sequence[str] = (),
    ) -> Self:
        del semantic_weight, pixel_count, source_color_ids
        normalized_seed = color_registry.display_color(seed_hex)
        palette_tones = tuple(int(value) for value in (tones or _default_tonal_stops(palette_type)))
        tone_models = tuple(
            ToneStopModel.from_color(
                int(tone_value),
                color_registry.tonal_color(
                    normalized_seed,
                    float(tone_value),
                    chroma_override=chroma_override,
                ),
                token=f"{palette_id}:{int(tone_value)}",
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
            tones=tone_models,
        )

    def __iter__(self) -> Iterator[ToneStopModel]:
        return iter(self.tones)

    def seed_rgb(self) -> tuple[int, int, int]:
        return color_registry.format_color(self.seed_hex, "rgb")

    def seed_tone(self) -> int:
        return int(round(color_registry.hct_of(self.seed_hex)[2]))

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
            "role_bias": self.role_bias.value,
            "seed_name": self.seed_name,
            "seed_color_id": self.seed_color_id,
            "seed_hex": self.seed_hex,
            "display_name": self.display_name,
            "seed_display_name": self.seed_display_name,
            "seed_family_name": self.seed_family_name,
            "tones": [tone.to_dict() for tone in self.tones],
        }


@dataclass(frozen=True, slots=True)
class ColorSchemeModel:
    palettes: tuple[TonalPaletteModel, ...] = field(default_factory=tuple)
    max_palettes: int = _MAX_PALETTES

    def __post_init__(self) -> None:
        palettes = tuple(self.palettes)
        if not any(palette.palette_type == ColorFamilyType.ACHROMATIC for palette in palettes):
            palettes = (self._fallback_achromatic_palette(), *palettes)
        object.__setattr__(self, "palettes", self._annotate_names(palettes[: self.max_palettes]))

    @classmethod
    def build(
        cls,
        *,
        achromatic_seed: Mapping[str, Any] | None = None,
        chromatic_seeds: Sequence[Mapping[str, Any]] = (),
        max_palettes: int = _MAX_PALETTES,
    ) -> Self:
        palettes: list[TonalPaletteModel] = []
        if achromatic_seed is not None:
            palettes.append(cls._palette_from_seed_spec(achromatic_seed, palette_index=1))
        palettes.extend(
            cls._palette_from_seed_spec(seed, palette_index=index)
            for index, seed in enumerate(chromatic_seeds[: max(0, max_palettes - 1)], start=1)
        )
        return cls(palettes=tuple(palettes), max_palettes=max_palettes)

    @staticmethod
    def _palette_from_seed_spec(seed: Mapping[str, Any], *, palette_index: int) -> TonalPaletteModel:
        palette_type = _coerce_palette_type(seed.get("palette_type") or ColorFamilyType.CHROMATIC)
        return TonalPaletteModel.from_seed(
            palette_id=f"palette-{palette_type.value}-{palette_index}",
            palette_type=palette_type,
            seed_hex=str(seed.get("seed_hex") or "#ffffff"),
            role_bias=seed.get("role_bias") or PaletteRoleBias.MIXED,
            seed_name=seed.get("seed_name"),
            seed_color_id=seed.get("seed_color_id"),
            chroma_override=(
                _ACHROMATIC_PALETTE_CHROMA
                if palette_type == ColorFamilyType.ACHROMATIC
                else None
            ),
        )

    @staticmethod
    def _fallback_achromatic_palette() -> TonalPaletteModel:
        return TonalPaletteModel.from_seed(
            palette_id="palette-achromatic-1",
            palette_type=ColorFamilyType.ACHROMATIC,
            seed_hex="#ffffff",
            role_bias=PaletteRoleBias.BACKGROUND,
            seed_name="white",
            chroma_override=_ACHROMATIC_PALETTE_CHROMA,
        )

    @classmethod
    def _annotate_names(cls, palettes: tuple[TonalPaletteModel, ...]) -> tuple[TonalPaletteModel, ...]:
        family_names = [
            _family_palette_name(palette.seed_name, palette_type=palette.palette_type)
            for palette in palettes
        ]
        family_counts = Counter(family_names)
        annotated: list[TonalPaletteModel] = []
        for palette, family_name in zip(palettes, family_names):
            specific_name = _specific_palette_name(palette.seed_name)
            if palette.palette_type == ColorFamilyType.ACHROMATIC:
                annotated.append(
                    replace(
                        palette,
                        display_name="Neutral",
                        seed_display_name=specific_name,
                        seed_family_name="Neutral",
                    )
                )
                continue
            display_name = family_name if family_counts[family_name] <= 1 else (specific_name or family_name)
            annotated.append(
                replace(
                    palette,
                    display_name=display_name,
                    seed_display_name=specific_name,
                    seed_family_name=family_name,
                )
            )
        return tuple(annotated)

    @property
    def achromatic_palette(self) -> TonalPaletteModel | None:
        return next(
            (palette for palette in self.palettes if palette.palette_type == ColorFamilyType.ACHROMATIC),
            None,
        )

    @property
    def chromatic_palettes(self) -> tuple[TonalPaletteModel, ...]:
        return tuple(
            palette
            for palette in self.palettes
            if palette.palette_type == ColorFamilyType.CHROMATIC
        )

    def __iter__(self) -> Iterator[TonalPaletteModel]:
        return iter(self.palettes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "achromatic_palette": (
                self.achromatic_palette.to_dict() if self.achromatic_palette else None
            ),
            "chromatic_palettes": [palette.to_dict() for palette in self.chromatic_palettes],
            "max_palettes": self.max_palettes,
            "selected_palettes": len(self.palettes),
        }
