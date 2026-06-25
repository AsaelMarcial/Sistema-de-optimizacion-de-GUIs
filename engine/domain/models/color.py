from __future__ import annotations

from typing import Any, Iterable

from coloraide.everything import ColorAll

from engine.adapters.color_service import color_registry


class Color(ColorAll):
    def __init__(
        self,
        red: float | None = None,
        green: float | None = None,
        blue: float | None = None,
        alpha: float = 1.0,
    ) -> None:
        if isinstance(red, str) and green is not None and not isinstance(green, int):
            super().__init__(red, green, blue if blue is not None else alpha)
            return

        if green is None and blue is None:
            source: Any = red
        else:
            source = (int(red), int(green or 0), int(blue or 0), float(alpha))

        parsed = color_registry.display_color(source)
        super().__init__("srgb", parsed.coords(), alpha=float(parsed.alpha()))

def unique_colors(values: Iterable[Color | None]) -> tuple[Color, ...]:
    return tuple(dict.fromkeys(color for color in values if color is not None))
