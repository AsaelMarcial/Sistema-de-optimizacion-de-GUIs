from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import math
import re
from typing import Literal, Protocol, TypeAlias, cast, overload

from coloraide.everything import ColorAll

RGBColor: TypeAlias = tuple[int, int, int]
RGBAColor: TypeAlias = tuple[int, int, int, float]
HCTColor: TypeAlias = tuple[float, float, float]
ColorLike: TypeAlias = ColorAll | str | Sequence[int | float]
FormatName: TypeAlias = Literal["hex", "rgb", "rgba", "css", "hct"]
FormatResult: TypeAlias = str | RGBColor | RGBAColor | HCTColor
_MULTISPACE_RE = re.compile(r"\s+")
_RGBA_ALPHA_RE = re.compile(r"^rgba\((.+)\)$", re.IGNORECASE)
_HSLA_ALPHA_RE = re.compile(r"^hsla\((.+)\)$", re.IGNORECASE)
_SPACE_ALPHA_COLOR_RE = re.compile(r"^(?:rgb|hsl)\((.+)/(.+)\)$", re.IGNORECASE)
_CSS_COLOR_KEYWORDS = frozenset(
    {
        "currentcolor",
        "inherit",
        "initial",
        "unset",
        "revert",
        "revert-layer",
    }
)


def _bounded_rgb_channels(color: ColorAll) -> RGBColor:
    red, green, blue = color.coords()
    return (
        max(0, min(255, round(red * 255))),
        max(0, min(255, round(green * 255))),
        max(0, min(255, round(blue * 255))),
    )


def _sanitize_hue(hue: float, chroma: float, *, digits: int = 4) -> float:
    if not math.isfinite(chroma) or abs(chroma) < 1e-9:
        return 0.0
    if not math.isfinite(hue):
        return 0.0
    return round(float(hue) % 360.0, digits)


def _sanitize_scalar(value: float, *, digits: int = 4) -> float:
    if not math.isfinite(value):
        return 0.0
    return round(float(value), digits)


def _alpha_is_zero(raw_alpha: str) -> bool:
    alpha = raw_alpha.strip().rstrip(")")
    if alpha.endswith("%"):
        try:
            return float(alpha[:-1].strip()) == 0
        except ValueError:
            return False
    try:
        return float(alpha) == 0
    except ValueError:
        return False


def _as_string(formatted: FormatResult, *, strategy_name: str) -> str:
    if not isinstance(formatted, str):
        raise TypeError(f"La strategy '{strategy_name}' debe devolver un string")
    return formatted


def _as_rgb(formatted: FormatResult) -> RGBColor:
    if (
        not isinstance(formatted, tuple)
        or len(formatted) != 3
        or not all(isinstance(channel, int) for channel in formatted)
    ):
        raise TypeError("La strategy 'rgb' debe devolver una tupla RGB")
    return cast(RGBColor, formatted)


def _as_rgba(formatted: FormatResult) -> RGBAColor:
    if (
        not isinstance(formatted, tuple)
        or len(formatted) != 4
        or not isinstance(formatted[0], int)
        or not isinstance(formatted[1], int)
        or not isinstance(formatted[2], int)
        or not isinstance(formatted[3], float)
    ):
        raise TypeError("La strategy 'rgba' debe devolver una tupla RGBA")
    return cast(RGBAColor, formatted)


def _as_hct(formatted: FormatResult) -> HCTColor:
    if (
        not isinstance(formatted, tuple)
        or len(formatted) != 3
        or not isinstance(formatted[0], float)
        or not isinstance(formatted[1], float)
        or not isinstance(formatted[2], float)
    ):
        raise TypeError("La strategy 'hct' debe devolver una tupla HCT")
    return cast(HCTColor, formatted)


@dataclass(frozen=True)
class ColorFormatStrategy:
    name: FormatName
    digits: int = 4
    lowercase: bool = True

    def format(self, color: ColorAll) -> FormatResult:
        if self.name == "hex":
            value = color.to_string(hex=True)
            return value.lower() if self.lowercase else value

        if self.name == "rgb":
            return _bounded_rgb_channels(color)

        if self.name == "rgba":
            red, green, blue = _bounded_rgb_channels(color)
            return red, green, blue, round(float(color.alpha()), self.digits)

        if self.name == "hct":
            hue, chroma, tone = color.convert("hct").coords()
            return (
                _sanitize_hue(float(hue), float(chroma), digits=self.digits),
                _sanitize_scalar(float(chroma), digits=self.digits),
                _sanitize_scalar(float(tone), digits=self.digits),
            )

        red, green, blue = _bounded_rgb_channels(color)
        alpha = round(float(color.alpha()), self.digits)
        if alpha <= 0:
            return "transparent"
        if alpha >= 1:
            return f"rgb({red}, {green}, {blue})"
        return f"rgba({red}, {green}, {blue}, {alpha})"


class _FormatRegistryProtocol(Protocol):
    gamut_strategy: str
    rgb_match_strategy: str
    hex_match_strategy: str

    def get_gamut(self, name: str):
        ...

    def get_formatter(self, name: FormatName) -> ColorFormatStrategy:
        ...

    def match_color(self, value: str, *, strategy_name: str) -> ColorAll | None:
        ...


class FormatOperationsMixin:
    def parse_color(self, value: ColorLike) -> ColorAll:
        if isinstance(value, ColorAll):
            return value.clone()

        if isinstance(value, str):
            return ColorAll(value)

        channels = [float(channel) for channel in value]
        if len(channels) == 3:
            red, green, blue = channels
            return ColorAll("srgb", [red / 255.0, green / 255.0, blue / 255.0])

        if len(channels) == 4:
            red, green, blue, alpha = channels
            return ColorAll("srgb", [red / 255.0, green / 255.0, blue / 255.0], alpha=alpha)

        raise ValueError(f"Formato de color no soportado: {value!r}")

    def display_color(self, value: ColorLike, *, gamut_strategy: str | None = None) -> ColorAll:
        registry = cast(_FormatRegistryProtocol, self)
        converted = self.parse_color(value).convert("srgb")
        gamut = registry.get_gamut(gamut_strategy or registry.gamut_strategy)
        return gamut.fit(converted, space="srgb")

    @overload
    def format_color(
        self,
        value: ColorLike,
        format_name: Literal["hex", "css"],
        *,
        gamut_strategy: str | None = None,
    ) -> str: ...

    @overload
    def format_color(
        self,
        value: ColorLike,
        format_name: Literal["rgb"],
        *,
        gamut_strategy: str | None = None,
    ) -> RGBColor: ...

    @overload
    def format_color(
        self,
        value: ColorLike,
        format_name: Literal["hct"],
        *,
        gamut_strategy: str | None = None,
    ) -> HCTColor: ...

    @overload
    def format_color(
        self,
        value: ColorLike,
        format_name: Literal["rgba"],
        *,
        gamut_strategy: str | None = None,
    ) -> RGBAColor: ...

    def format_color(
        self,
        value: ColorLike,
        format_name: FormatName,
        *,
        gamut_strategy: str | None = None,
    ) -> FormatResult:
        registry = cast(_FormatRegistryProtocol, self)
        formatter = registry.get_formatter(format_name)
        source = (
            self.parse_color(value)
            if format_name == "hct"
            else self.display_color(value, gamut_strategy=gamut_strategy)
        )
        formatted = formatter.format(source)

        if format_name in {"hex", "css"}:
            return _as_string(formatted, strategy_name=format_name)
        if format_name == "rgb":
            return _as_rgb(formatted)
        if format_name == "hct":
            return _as_hct(formatted)
        return _as_rgba(formatted)

    def alpha_of(self, value: ColorLike, *, digits: int = 4) -> float:
        return round(float(self.parse_color(value).alpha()), digits)

    def hct_of(self, value: ColorLike) -> HCTColor:
        return self.format_color(value, "hct")

    def tone_of(self, value: ColorLike) -> float:
        return self.hct_of(value)[2]

    def signature_of(self, value: ColorLike) -> tuple[str, float]:
        return self.format_color(value, "hex"), self.alpha_of(value)

    def is_transparent_color(self, value: ColorLike) -> bool:
        try:
            return self.alpha_of(value) <= 0.0
        except Exception:
            return False

    def normalize_css_color(self, value: ColorLike) -> str:
        if self.is_transparent_color(value):
            return "transparent"
        return self.format_color(value, "css")

    def is_alpha_zero_color(self, value: str) -> bool:
        normalized = str(value or "").strip().lower()
        if not normalized:
            return False
        if normalized == "transparent":
            return True

        hex_value = normalized.lstrip("#")
        if len(hex_value) in {4, 8}:
            alpha = hex_value[-1] if len(hex_value) == 4 else hex_value[-2:]
            return alpha in {"0", "00"}

        rgba_match = _RGBA_ALPHA_RE.match(normalized)
        if rgba_match:
            parts = [part.strip() for part in rgba_match.group(1).split(",")]
            return len(parts) >= 4 and _alpha_is_zero(parts[3])

        hsla_match = _HSLA_ALPHA_RE.match(normalized)
        if hsla_match:
            parts = [part.strip() for part in hsla_match.group(1).split(",")]
            return len(parts) >= 4 and _alpha_is_zero(parts[3])

        slash_match = _SPACE_ALPHA_COLOR_RE.match(normalized)
        if slash_match:
            return _alpha_is_zero(slash_match.group(2))

        return False

    def normalize_css_color_token(self, value: str) -> str:
        normalized = _MULTISPACE_RE.sub(" ", str(value).strip()).strip()
        if not normalized:
            return normalized

        lower = normalized.lower()
        if lower == "transparent" or self.is_alpha_zero_color(lower):
            return "transparent"
        if lower in _CSS_COLOR_KEYWORDS:
            return lower

        try:
            return self.format_color(normalized, "css")
        except Exception:
            return lower if lower.startswith("#") else normalized

    def variants(self, value: ColorLike) -> tuple[str, ...]:
        normalized = str(value or "").strip()
        if not normalized:
            return ()

        variants = {normalized.lower()}
        try:
            variants.add(self.format_color(normalized, "hex").lower())
            variants.add(self.format_color(self.format_color(normalized, "rgb"), "css").lower())
        except Exception:
            pass
        return tuple(sorted(variants))

    def parseable_variants(self, value: ColorLike) -> tuple[str, ...]:
        normalized = str(value or "").strip()
        if not normalized:
            return ()

        try:
            return tuple(
                sorted(
                    {
                        normalized.lower(),
                        self.format_color(normalized, "hex").lower(),
                        self.format_color(self.format_color(normalized, "rgb"), "css").lower(),
                    }
                )
            )
        except Exception:
            return ()

    def _match_and_format(
        self,
        value: str,
        *,
        strategy_name: str,
        format_name: Literal["rgb", "rgba", "hex", "css"],
    ) -> FormatResult | None:
        registry = cast(_FormatRegistryProtocol, self)
        color = registry.match_color(value, strategy_name=strategy_name)
        if color is None:
            return None
        return self.format_color(color, format_name)

    def rgb_string_to_tuple(self, color_str: str) -> RGBColor | None:
        registry = cast(_FormatRegistryProtocol, self)
        rgb = self._match_and_format(
            color_str,
            strategy_name=registry.rgb_match_strategy,
            format_name="rgb",
        )
        return cast(RGBColor | None, rgb)

    def hex_to_rgb(self, hex_color: str) -> RGBColor | None:
        registry = cast(_FormatRegistryProtocol, self)
        rgb = self._match_and_format(
            hex_color,
            strategy_name=registry.hex_match_strategy,
            format_name="rgb",
        )
        return cast(RGBColor | None, rgb)
