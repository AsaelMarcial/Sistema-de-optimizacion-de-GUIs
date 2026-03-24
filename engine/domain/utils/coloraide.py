from __future__ import annotations

import math
import re
from typing import Sequence, TypeAlias

from coloraide.everything import ColorAll

ColorLike: TypeAlias = ColorAll | str | Sequence[int | float]
RGBColor: TypeAlias = tuple[int, int, int]
_RGB_PATTERN = re.compile(r"rgba?\(([^\)]+)\)", re.IGNORECASE)


def _display_srgb_color(value: ColorLike) -> ColorAll:
    return parse_color(value).convert("srgb").fit(space="srgb", method="hct-chroma")


def display_color(value: ColorLike) -> ColorAll:
    return _display_srgb_color(value)


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


def parse_color(value: ColorLike) -> ColorAll:
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


def color_to_hex(value: ColorLike) -> str:
    return _display_srgb_color(value).to_string(hex=True).lower()


def color_to_rgb_tuple(value: ColorLike) -> tuple[int, int, int]:
    red, green, blue = _display_srgb_color(value).coords()
    return (
        max(0, min(255, round(red * 255))),
        max(0, min(255, round(green * 255))),
        max(0, min(255, round(blue * 255))),
    )


def color_to_rgba_tuple(value: ColorLike) -> tuple[int, int, int, float]:
    color = _display_srgb_color(value)
    red, green, blue = color_to_rgb_tuple(color)
    return red, green, blue, round(float(color.alpha()), 4)


def alpha_value(value: ColorLike) -> float:
    return round(float(parse_color(value).alpha()), 4)


def rounded_coords(coords: Sequence[float], *, digits: int = 4) -> tuple[float, ...]:
    return tuple(round(float(channel), digits) for channel in coords)


def hct_coords(value: ColorLike) -> tuple[float, float, float]:
    hue, chroma, tone = parse_color(value).convert("hct").coords()
    return (
        _sanitize_hue(float(hue), float(chroma)),
        _sanitize_scalar(float(chroma)),
        _sanitize_scalar(float(tone)),
    )


def hsl_percent_coords(value: ColorLike) -> tuple[float, float, float]:
    hue, saturation, lightness = parse_color(value).convert("hsl").coords()
    return (
        round(float(hue), 4),
        round(float(saturation) * 100, 4),
        round(float(lightness) * 100, 4),
    )


def hsv_percent_coords(value: ColorLike) -> tuple[float, float, float]:
    hue, saturation, brightness = parse_color(value).convert("hsv").coords()
    return (
        round(float(hue), 4),
        round(float(saturation) * 100, 4),
        round(float(brightness) * 100, 4),
    )


def hct_color(hue: float, chroma: float, tone: float, *, alpha: float = 1.0) -> ColorAll:
    return ColorAll("hct", [float(hue), float(chroma), float(tone)], alpha=float(alpha))


def tonal_palette_color(
    value: ColorLike,
    tone: float,
    *,
    target_space: str = "srgb",
    chroma_override: float | None = None,
) -> ColorAll:
    seed = parse_color(value).convert("hct")
    tonal = seed.clone()
    if chroma_override is not None:
        tonal.set("chroma", float(chroma_override))
    tonal.set("tone", float(tone))
    return tonal.fit(target_space, method="raytrace", pspace="hct")


def delta_e_distance(
    left: ColorLike,
    right: ColorLike,
    *,
    method: str = "2000",
) -> float:
    return float(parse_color(left).delta_e(parse_color(right), method=method))


def contrast_ratio(foreground: ColorLike, background: ColorLike) -> float:
    return float(parse_color(foreground).contrast(parse_color(background)))


def composite_over(foreground: ColorLike, background: ColorLike) -> ColorAll:
    fg = parse_color(foreground).convert("srgb")
    bg = parse_color(background).convert("srgb")

    fg_red, fg_green, fg_blue = fg.coords()
    bg_red, bg_green, bg_blue = bg.coords()
    fg_alpha = float(fg.alpha())
    bg_alpha = float(bg.alpha())

    out_alpha = fg_alpha + (bg_alpha * (1.0 - fg_alpha))
    if out_alpha <= 0:
        return ColorAll("srgb", [0.0, 0.0, 0.0], alpha=0.0)

    out_red = ((fg_red * fg_alpha) + (bg_red * bg_alpha * (1.0 - fg_alpha))) / out_alpha
    out_green = ((fg_green * fg_alpha) + (bg_green * bg_alpha * (1.0 - fg_alpha))) / out_alpha
    out_blue = ((fg_blue * fg_alpha) + (bg_blue * bg_alpha * (1.0 - fg_alpha))) / out_alpha

    return ColorAll("srgb", [out_red, out_green, out_blue], alpha=out_alpha)


def rgb_string_to_tuple(color_str: str) -> RGBColor | None:
    if not color_str:
        return None

    match = _RGB_PATTERN.search(color_str.strip())
    if not match:
        return None

    parts = [part.strip() for part in match.group(1).split(",")]
    if len(parts) < 3:
        return None

    try:
        return tuple(int(float(channel)) for channel in parts[:3])  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def hex_to_rgb(hex_color: str) -> RGBColor | None:
    if not hex_color:
        return None

    normalized = hex_color.strip().lstrip("#")
    if len(normalized) == 3:
        normalized = "".join(char * 2 for char in normalized)

    if len(normalized) != 6:
        return None

    try:
        return tuple(int(normalized[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def rgb_to_css(rgb: RGBColor) -> str:
    return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"


def is_light_color(rgb: RGBColor) -> bool:
    red, green, blue = rgb
    brightness = (red * 299 + green * 587 + blue * 114) / 1000
    return brightness > 180


def luminance(rgb: RGBColor) -> float:
    red, green, blue = [channel / 255.0 for channel in rgb]
    return 0.2126 * (red**3) + 0.7152 * (green**3) + 0.0722 * (blue**3)


def brighten_color(rgb: RGBColor, target_contrast: float, background_rgb: RGBColor) -> RGBColor:
    new_rgb = list(rgb)
    attempts = 0
    max_attempts = 25

    while contrast_ratio(tuple(new_rgb), background_rgb) < target_contrast and attempts < max_attempts:
        if luminance(tuple(new_rgb)) > luminance(background_rgb):
            new_rgb = [max(0, channel - 10) for channel in new_rgb]
        else:
            new_rgb = [min(255, channel + 10) for channel in new_rgb]
        attempts += 1

    return tuple(new_rgb)  # type: ignore[return-value]
