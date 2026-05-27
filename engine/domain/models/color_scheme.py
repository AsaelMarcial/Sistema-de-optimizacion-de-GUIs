from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator, Sequence, Self

from engine.adapters.color_service import color_registry
from engine.domain.enums.types.color import ColorFamilyType
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
    100,
)
_DEFAULT_CHROMATIC_TONAL_STOPS: tuple[int, ...] = (10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98)
_MAX_PALETTES = 12


def _coerce_palette_type(value: ColorFamilyType | str) -> ColorFamilyType:
    if isinstance(value, ColorFamilyType):
        return value
    return ColorFamilyType(str(value).strip().lower())


def _default_tonal_stops(palette_type: ColorFamilyType | str) -> tuple[int, ...]:
    if _coerce_palette_type(palette_type) == ColorFamilyType.CHROMATIC:
        return _DEFAULT_CHROMATIC_TONAL_STOPS
    return _DEFAULT_ACHROMATIC_TONAL_STOPS


@dataclass(frozen=True, slots=True)
class ToneStop:
    tone: int
    hex_value: str
    rgb: tuple[int, int, int]
    hct: tuple[float, float, float]
    token: str | None = None

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
class TonalPalette:
    palette_id: str
    palette_type: ColorFamilyType
    label: str
    source_color_id: str | None = None
    tones: tuple[ToneStop, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "palette_type", _coerce_palette_type(self.palette_type))

    @classmethod
    def from_color(
        cls,
        *,
        palette_id: str,
        color: Color,
        label: str | None = None,
        tones: Sequence[int] | None = None,
    ) -> Self:
        return cls.from_value(
            palette_id=palette_id,
            palette_type=color.family_type,
            value=color.rgb,
            label=label or color.palette_label,
            source_color_id=color.color_id,
            tones=tones,
        )

    @classmethod
    def from_value(
        cls,
        *,
        palette_id: str,
        palette_type: ColorFamilyType | str,
        value: Any,
        label: str,
        source_color_id: str | None = None,
        tones: Sequence[int] | None = None,
    ) -> Self:
        palette_type_model = _coerce_palette_type(palette_type)
        seed = color_registry.display_color(value)
        return cls(
            palette_id=palette_id,
            palette_type=palette_type_model,
            label=label,
            source_color_id=source_color_id,
            tones=tuple(
                cls._tone_stop(palette_id=palette_id, seed=seed, tone=int(tone))
                for tone in (tones or _default_tonal_stops(palette_type_model))
            ),
        )

    @staticmethod
    def _tone_stop(*, palette_id: str, seed: Any, tone: int) -> ToneStop:
        tonal = color_registry.tonal_color(seed, float(tone))
        normalized = color_registry.display_color(tonal)
        return ToneStop(
            tone=tone,
            hex_value=color_registry.format_color(normalized, "hex"),
            rgb=color_registry.format_color(normalized, "rgb"),
            hct=color_registry.hct_of(normalized),  # type: ignore[arg-type]
            token=f"{palette_id}:{tone}",
        )

    def __iter__(self) -> Iterator[ToneStop]:
        return iter(self.tones)

    def nearest_tone_to(self, rgb: tuple[int, int, int]) -> tuple[ToneStop | None, float | None]:
        best_tone: ToneStop | None = None
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
            "label": self.label,
            "source_color_id": self.source_color_id,
            "tones": [tone.to_dict() for tone in self.tones],
        }


@dataclass(frozen=True, slots=True)
class ColorScheme:
    palettes: tuple[TonalPalette, ...] = field(default_factory=tuple)
    max_palettes: int = _MAX_PALETTES

    def __post_init__(self) -> None:
        palettes = tuple(self.palettes)
        if not any(palette.palette_type == ColorFamilyType.ACHROMATIC for palette in palettes):
            palettes = (self._base_palette(), *palettes)
        object.__setattr__(self, "palettes", palettes[: self.max_palettes])

    @classmethod
    def build(
        cls,
        colors: Iterable[Color],
        *,
        max_palettes: int = _MAX_PALETTES,
    ) -> Self:
        source_colors = tuple(colors)
        palettes: list[TonalPalette] = []
        achromatic_color = next(
            (color for color in source_colors if color.family_type == ColorFamilyType.ACHROMATIC),
            None,
        )
        if achromatic_color is not None:
            palettes.append(
                TonalPalette.from_color(
                    palette_id="palette-achromatic-1",
                    color=achromatic_color,
                    label="Neutral",
                )
            )

        chromatic_colors = (
            color for color in source_colors if color.family_type == ColorFamilyType.CHROMATIC
        )
        palettes.extend(
            TonalPalette.from_color(
                palette_id=f"palette-chromatic-{index}",
                color=color,
            )
            for index, color in enumerate(chromatic_colors, start=1)
        )
        return cls(palettes=tuple(palettes), max_palettes=max_palettes)

    @staticmethod
    def _base_palette() -> TonalPalette:
        return TonalPalette.from_value(
            palette_id="palette-achromatic-1",
            palette_type=ColorFamilyType.ACHROMATIC,
            value="#ffffff",
            label="Neutral",
        )

    @property
    def achromatic_palette(self) -> TonalPalette | None:
        return next(
            (palette for palette in self.palettes if palette.palette_type == ColorFamilyType.ACHROMATIC),
            None,
        )

    @property
    def chromatic_palettes(self) -> tuple[TonalPalette, ...]:
        return tuple(
            palette
            for palette in self.palettes
            if palette.palette_type == ColorFamilyType.CHROMATIC
        )

    def map_colors(self, colors: Sequence[Color]) -> tuple[Color, ...]:
        return tuple(self._map_color(color) for color in colors)

    def _map_color(self, color: Color) -> Color:
        palette = self._source_palette_for(color) or self._nearest_palette_for(color)
        if palette is None:
            return color
        tone_stop, distance = palette.nearest_tone_to(color.rgb)
        if tone_stop is None or distance is None:
            return color
        return color.set_palette_mapping(
            palette_id=palette.palette_id,
            tone=tone_stop.tone,
        )

    def _source_palette_for(self, color: Color) -> TonalPalette | None:
        return next(
            (
                palette
                for palette in self.palettes
                if palette.source_color_id is not None and palette.source_color_id == color.color_id
            ),
            None,
        )

    def _nearest_palette_for(self, color: Color) -> TonalPalette | None:
        best_palette: TonalPalette | None = None
        best_distance: float | None = None
        for palette in self._candidate_palettes_for(color):
            _, distance = palette.nearest_tone_to(color.rgb)
            if distance is None:
                continue
            if best_distance is None or distance < best_distance:
                best_palette = palette
                best_distance = distance
        return best_palette

    def _candidate_palettes_for(self, color: Color) -> tuple[TonalPalette, ...]:
        if color.family_type == ColorFamilyType.ACHROMATIC:
            return (self.achromatic_palette,) if self.achromatic_palette else ()
        return self.chromatic_palettes or (
            (self.achromatic_palette,) if self.achromatic_palette else ()
        )

    def __iter__(self) -> Iterator[TonalPalette]:
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
