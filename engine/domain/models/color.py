from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Self

from engine.adapters.color_service import color_registry
from engine.domain.data.web_colors import get_web_color, nearest_web_color
from engine.domain.enums.types.color import ColorFamilyType

_ACHROMATIC_CHROMA_THRESHOLD = 8.0
_FAMILY_COMPARISON_TONE = 60.0
_FAMILY_HUE_DELTA_THRESHOLD = 12.0
_FAMILY_CHROMA_DELTA_THRESHOLD = 30.0
_FAMILY_NORMALIZED_DELTA_E_THRESHOLD = 10.0
_FAMILY_FALLBACK_MATCH_DELTA_E = 6.0


def _coerce_color_family_type(value: ColorFamilyType | str | None) -> ColorFamilyType:
    if isinstance(value, ColorFamilyType):
        return value
    normalized = str(value or ColorFamilyType.CHROMATIC.value).strip().lower()
    return ColorFamilyType(normalized)


@dataclass(slots=True)
class Color:
    color_id: str
    rgb_value: str
    alpha: float
    family_type: ColorFamilyType
    element_usage_count: int = 0
    nearest_web_color: str | None = None
    pixel_count: int = 0
    pixel_percentage: float = 0.0
    palette_id: str | None = None
    tone: int | None = None
    token: str | None = None

    def __post_init__(self) -> None:
        self.family_type = _coerce_color_family_type(self.family_type)

    @classmethod
    def from_rgb(cls, *, color_id: str, rgb_value: str) -> Self:
        rgb = color_registry.format_color(rgb_value, "rgb")
        hct = color_registry.hct_of(rgb_value)
        nearest_match = nearest_web_color(rgb)
        return cls(
            color_id=str(color_id or "").strip(),
            rgb_value=color_registry.format_color(rgb_value, "css"),
            alpha=color_registry.alpha_of(rgb_value),
            family_type=_family_type_for_hct(hct[1]),
            nearest_web_color=nearest_match.color_name,
        )

    @property
    def rgb(self) -> tuple[int, int, int]:
        return color_registry.format_color(self.rgb_value, "rgb")

    @property
    def hex_value(self) -> str:
        return color_registry.format_color(self.rgb_value, "hex")

    @property
    def hct(self) -> tuple[float, float, float]:
        return color_registry.hct_of(self.rgb_value)

    def signature(self) -> tuple[str, float]:
        return self.hex_value, round(self.alpha, 4)

    @property
    def palette_label(self) -> str:
        if self.family_type == ColorFamilyType.ACHROMATIC:
            return "Neutral"
        if not self.nearest_web_color:
            return "Chromatic"
        try:
            return get_web_color(self.nearest_web_color).family_display_name
        except Exception:
            return self.nearest_web_color.replace("_", " ").title()

    @property
    def broad_family_name(self) -> str | None:
        if self.family_type == ColorFamilyType.ACHROMATIC:
            return "Neutral"
        if not self.nearest_web_color:
            return None
        try:
            return get_web_color(self.nearest_web_color).wikipedia_family
        except Exception:
            return None

    def increment_usage(self) -> Self:
        self.element_usage_count += 1
        return self

    def set_palette_mapping(self, *, palette_id: str, tone: int) -> Self:
        self.palette_id = str(palette_id or "").strip() or None
        self.tone = int(tone)
        return self

    def set_pixel_count(self, count: int, percentage: float | None = None) -> Self:
        self.pixel_count = int(count)
        if percentage is not None:
            self.pixel_percentage = float(percentage)
        return self

    def set_token_assignment(self, token_id: str) -> Self:
        normalized_token_id = str(token_id or "").strip()
        if normalized_token_id:
            self.token = normalized_token_id
        return self

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "color_id": self.color_id,
            "rgb_value": self.rgb_value,
            "alpha": self.alpha,
            "family_type": self.family_type.value,
            "element_usage_count": self.element_usage_count,
            "hex_value": self.hex_value,
            "rgb": list(self.rgb),
            "hct": list(self.hct),
        }
        if self.nearest_web_color is not None:
            payload["nearest_web_color"] = self.nearest_web_color
        if self.pixel_count:
            payload["pixel_count"] = self.pixel_count
        if self.pixel_percentage:
            payload["pixel_percentage"] = self.pixel_percentage
        if self.palette_id is not None:
            payload["palette_id"] = self.palette_id
        if self.tone is not None:
            payload["tone"] = self.tone
        if self.token is not None:
            payload["token"] = self.token
        return payload


@dataclass(slots=True)
class ColorCatalog:
    colors: tuple[Color, ...] = field(default_factory=tuple)

    def add_color(self, rgb_value: str) -> str:
        normalized = color_registry.format_color(rgb_value, "css")
        existing = self.entry_by_value(normalized)
        if existing is not None:
            existing.increment_usage()
            return existing.color_id

        color = Color.from_rgb(
            color_id=f"color-{len(self.colors) + 1}",
            rgb_value=normalized,
        ).increment_usage()
        self.colors = (*self.colors, color)
        return color.color_id

    def __iter__(self) -> Iterator[Color]:
        return iter(self.colors)

    def __len__(self) -> int:
        return len(self.colors)

    def entry_by_id(self, color_id: str) -> Color | None:
        normalized = str(color_id or "").strip()
        return next((entry for entry in self.colors if entry.color_id == normalized), None)

    def entry_by_value(self, value: str) -> Color | None:
        try:
            hex_value = color_registry.format_color(value, "hex")
            alpha = color_registry.alpha_of(value)
        except Exception:
            return None
        return next(
            (
                entry
                for entry in self.colors
                if entry.hex_value == hex_value and round(entry.alpha, 4) == round(alpha, 4)
            ),
            None,
        )

    def supported_scheme_colors(self) -> tuple[Color, ...]:
        return tuple(entry for entry in self.colors if entry.element_usage_count > 0)

    def scheme_palette_sources(self, *, max_palettes: int = 12) -> tuple[Color, ...]:
        sorted_entries = sorted(
            self.supported_scheme_colors(),
            key=lambda entry: (entry.pixel_count, entry.element_usage_count),
            reverse=True,
        )
        achromatic: list[Color] = []
        chromatic: list[Color] = []
        for entry in sorted_entries:
            target = achromatic if entry.family_type == ColorFamilyType.ACHROMATIC else chromatic
            if any(_same_palette_family(seed, entry) for seed in target):
                continue
            target.append(entry)
        return tuple((*achromatic[:1], *chromatic[: max(0, max_palettes - 1)]))

    def to_dict(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.colors]


def _family_type_for_hct(hct_chroma: float) -> ColorFamilyType:
    return (
        ColorFamilyType.ACHROMATIC
        if hct_chroma < _ACHROMATIC_CHROMA_THRESHOLD
        else ColorFamilyType.CHROMATIC
    )


def _hue_distance(left_hue: float, right_hue: float) -> float:
    distance = abs(float(left_hue) - float(right_hue)) % 360.0
    return min(distance, 360.0 - distance)


def _comparison_signature(value: Any) -> tuple[tuple[int, int, int], tuple[float, float, float]]:
    comparison_color = color_registry.tonal_color(value, _FAMILY_COMPARISON_TONE)
    return (
        color_registry.format_color(comparison_color, "rgb"),
        color_registry.hct_of(comparison_color),
    )  # type: ignore[arg-type]


def _same_palette_family(seed: Color, candidate: Color) -> bool:
    if seed.family_type != candidate.family_type:
        return False
    if candidate.family_type == ColorFamilyType.CHROMATIC:
        if (
            seed.broad_family_name
            and candidate.broad_family_name
            and seed.broad_family_name != candidate.broad_family_name
        ):
            return False
        seed_rgb, seed_hct = _comparison_signature(seed.rgb)
        candidate_rgb, candidate_hct = _comparison_signature(candidate.rgb)
        normalized_distance = color_registry.delta_e_distance(seed_rgb, candidate_rgb, method="2000")
        hue_delta = _hue_distance(seed_hct[0], candidate_hct[0])
        chroma_delta = abs(float(seed_hct[1]) - float(candidate_hct[1]))
        if (
            hue_delta <= _FAMILY_HUE_DELTA_THRESHOLD
            and chroma_delta <= _FAMILY_CHROMA_DELTA_THRESHOLD
            and normalized_distance <= _FAMILY_NORMALIZED_DELTA_E_THRESHOLD
        ):
            return True
    distance = color_registry.delta_e_distance(seed.rgb, candidate.rgb, method="2000")
    return distance <= _FAMILY_FALLBACK_MATCH_DELTA_E or (
        seed.nearest_web_color is not None
        and seed.nearest_web_color == candidate.nearest_web_color
        and distance <= 10.0
    )
