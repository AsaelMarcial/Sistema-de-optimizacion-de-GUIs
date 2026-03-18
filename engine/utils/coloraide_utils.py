from __future__ import annotations

import math
from typing import Sequence, TypeAlias

from coloraide.everything import ColorAll

ColorLike: TypeAlias = ColorAll | str | Sequence[int | float]


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
