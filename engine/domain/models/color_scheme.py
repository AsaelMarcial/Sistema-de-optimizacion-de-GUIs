from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from engine.domain.models.color import Color


@dataclass(frozen=True, slots=True)
class Tone:
    name: str
    value: int
    color: Color

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "color": self.color.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class Palette:
    name: str
    source_color: Color
    tones: tuple[Tone, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source_color": self.source_color.to_dict(),
            "tones": [tone.to_dict() for tone in self.tones],
        }


@dataclass(frozen=True, slots=True)
class ColorScheme:
    colors: tuple[Color, ...] = field(default_factory=tuple)
    palettes: tuple[Palette, ...] = field(default_factory=tuple)

    @classmethod
    def build(
        cls,
        colors: Iterable[Color] = (),
        *,
        palettes: Iterable[Palette] = (),
    ) -> "ColorScheme":
        return cls(
            colors=tuple(dict.fromkeys(colors)),
            palettes=tuple(palettes),
        )

    def __iter__(self):
        return iter(self.colors)

    def __len__(self) -> int:
        return len(self.colors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "colors": [color.to_dict() for color in self.colors],
            "palettes": [palette.to_dict() for palette in self.palettes],
        }
