from __future__ import annotations

import re
from typing import Iterable

RGBColor = tuple[int, int, int]

_RGB_PATTERN = re.compile(r"rgba?\(([^\)]+)\)", re.IGNORECASE)
_HEX_PATTERN = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}")


def parse_rgb(css_value: str) -> RGBColor:
    parsed = rgb_string_to_tuple(css_value)
    return parsed if parsed else (255, 255, 255)


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


def invert_rgb(rgb: RGBColor) -> RGBColor:
    return tuple(255 - value for value in rgb)  # type: ignore[return-value]


def is_light_color(rgb: RGBColor) -> bool:
    r, g, b = rgb
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return brightness > 180


def parse_inline_styles(style_str: str) -> dict[str, str]:
    styles: dict[str, str] = {}
    for item in style_str.split(";"):
        if ":" in item:
            key, value = item.split(":", 1)
            styles[key.strip()] = value.strip()
    return styles


def reconstruct_inline_style(styles_dict: dict[str, str]) -> str:
    return "; ".join(f"{key}: {value}" for key, value in styles_dict.items())


def rgb_to_luminance(rgb: RGBColor) -> float:
    def channel_luminance(channel: int) -> float:
        normalized = channel / 255.0
        return normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel_luminance(r) + 0.7152 * channel_luminance(g) + 0.0722 * channel_luminance(b)


def contrast_ratio(rgb1: RGBColor, rgb2: RGBColor) -> float:
    luminance_1 = rgb_to_luminance(rgb1)
    luminance_2 = rgb_to_luminance(rgb2)
    lighter, darker = max(luminance_1, luminance_2), min(luminance_1, luminance_2)
    return (lighter + 0.05) / (darker + 0.05)


def adjust_color_brightness(
    rgb: RGBColor,
    target_contrast: float,
    background_rgb: RGBColor,
    step: int = 10,
) -> RGBColor:
    new_rgb = list(rgb)
    attempts = 0
    max_attempts = 25

    while contrast_ratio(tuple(new_rgb), background_rgb) < target_contrast and attempts < max_attempts:
        if rgb_to_luminance(tuple(new_rgb)) > rgb_to_luminance(background_rgb):
            new_rgb = [max(0, channel - step) for channel in new_rgb]
        else:
            new_rgb = [min(255, channel + step) for channel in new_rgb]
        attempts += 1

    return tuple(new_rgb)  # type: ignore[return-value]


def brighten_color(rgb: RGBColor, target_contrast: float, background_rgb: RGBColor) -> RGBColor:
    return adjust_color_brightness(rgb, target_contrast, background_rgb)


def luminance(rgb: RGBColor) -> float:
    r, g, b = [channel / 255.0 for channel in rgb]
    return 0.2126 * (r**3) + 0.7152 * (g**3) + 0.0722 * (b**3)


def extract_hex_colors(text: str) -> Iterable[str]:
    return _HEX_PATTERN.findall(text)
