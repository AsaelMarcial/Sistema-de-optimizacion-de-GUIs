from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

_HEX_RE = re.compile(r"^#(?P<value>[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_RGB_RE = re.compile(r"^rgba?\((?P<parts>[^)]+)\)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class Color:
    red: int
    green: int
    blue: int
    alpha: float = 1.0

    def __post_init__(self) -> None:
        for channel_name in ("red", "green", "blue"):
            channel = int(getattr(self, channel_name))
            if not 0 <= channel <= 255:
                raise ValueError(f"{channel_name} must be between 0 and 255.")
            object.__setattr__(self, channel_name, channel)

        alpha = float(self.alpha)
        if not 0.0 <= alpha <= 1.0:
            raise ValueError("alpha must be between 0.0 and 1.0.")
        object.__setattr__(self, "alpha", alpha)

    @classmethod
    def from_css(cls, value: object) -> "Color | None":
        normalized = str(value or "").strip()
        if not normalized or normalized.lower() == "transparent":
            return None

        hex_match = _HEX_RE.match(normalized)
        if hex_match:
            raw = hex_match.group("value")
            if len(raw) in (3, 4):
                raw = "".join(channel * 2 for channel in raw)
            alpha = int(raw[6:8], 16) / 255 if len(raw) == 8 else 1.0
            return cls(
                red=int(raw[0:2], 16),
                green=int(raw[2:4], 16),
                blue=int(raw[4:6], 16),
                alpha=round(alpha, 4),
            )

        rgb_match = _RGB_RE.match(normalized)
        if not rgb_match:
            return None

        parts = [part.strip() for part in rgb_match.group("parts").split(",")]
        if len(parts) not in (3, 4):
            return None
        try:
            return cls(
                red=_parse_rgb_channel(parts[0]),
                green=_parse_rgb_channel(parts[1]),
                blue=_parse_rgb_channel(parts[2]),
                alpha=float(parts[3]) if len(parts) == 4 else 1.0,
            )
        except ValueError:
            return None

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self.red, self.green, self.blue

    @property
    def css(self) -> str:
        if self.alpha >= 1.0:
            return f"rgb({self.red}, {self.green}, {self.blue})"
        return f"rgba({self.red}, {self.green}, {self.blue}, {self.alpha:g})"

    @property
    def hex_value(self) -> str:
        if self.alpha >= 1.0:
            return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}{round(self.alpha * 255):02x}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "red": self.red,
            "green": self.green,
            "blue": self.blue,
            "alpha": self.alpha,
            "css": self.css,
            "hex": self.hex_value,
        }

    def __str__(self) -> str:
        return self.css


def unique_colors(values: Iterable[Color | None]) -> tuple[Color, ...]:
    return tuple(dict.fromkeys(color for color in values if color is not None))


def _parse_rgb_channel(value: str) -> int:
    if value.endswith("%"):
        percentage = float(value[:-1])
        if not 0 <= percentage <= 100:
            raise ValueError("RGB percentage channel is out of range.")
        return round((percentage / 100) * 255)
    return int(float(value))
