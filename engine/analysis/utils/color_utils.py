from __future__ import annotations

import re
from typing import Dict, Iterable, Optional, Tuple

RGBColor = Tuple[int, int, int]


_RGB_PATTERN = re.compile(r"rgba?\(([^\)]+)\)", re.IGNORECASE)
_HEX_PATTERN = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}")


def parse_rgb(css_value: str) -> RGBColor:
    """Convierte un valor CSS rgb/rgba a tupla RGB. Si falla, devuelve blanco."""
    parsed = rgb_string_to_tuple(css_value)
    return parsed if parsed else (255, 255, 255)


def rgb_string_to_tuple(color_str: str) -> Optional[RGBColor]:
    """Convierte strings rgb()/rgba() a RGB."""
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


def hex_to_rgb(hex_color: str) -> Optional[RGBColor]:
    """Convierte #RGB/#RRGGBB a tupla RGB."""
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


def parse_inline_styles(style_str: str) -> Dict[str, str]:
    styles = {}
    for item in style_str.split(";"):
        if ":" in item:
            key, value = item.split(":", 1)
            styles[key.strip()] = value.strip()
    return styles


def reconstruct_inline_style(styles_dict: Dict[str, str]) -> str:
    return "; ".join(f"{key}: {value}" for key, value in styles_dict.items())


def rgb_to_luminance(rgb: RGBColor) -> float:
    def channel_lum(channel: int) -> float:
        normalized = channel / 255.0
        return normalized / 12.92 if normalized <= 0.03928 else ((normalized + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel_lum(r) + 0.7152 * channel_lum(g) + 0.0722 * channel_lum(b)


def contrast_ratio(rgb1: RGBColor, rgb2: RGBColor) -> float:
    lum1 = rgb_to_luminance(rgb1)
    lum2 = rgb_to_luminance(rgb2)
    lighter, darker = max(lum1, lum2), min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


def adjust_color_brightness(rgb: RGBColor, target_contrast: float, bg_rgb: RGBColor, step: int = 10) -> RGBColor:
    new_rgb = list(rgb)
    attempts = 0
    max_attempts = 25

    while contrast_ratio(tuple(new_rgb), bg_rgb) < target_contrast and attempts < max_attempts:
        if rgb_to_luminance(tuple(new_rgb)) > rgb_to_luminance(bg_rgb):
            new_rgb = [max(0, channel - step) for channel in new_rgb]
        else:
            new_rgb = [min(255, channel + step) for channel in new_rgb]
        attempts += 1

    return tuple(new_rgb)  # type: ignore[return-value]


def brighten_color(rgb: RGBColor, target_contrast: float, bg_color: RGBColor) -> RGBColor:
    return adjust_color_brightness(rgb, target_contrast, bg_color)


def reduce_energy_intensity(rgb: RGBColor, factor: float = 0.5) -> RGBColor:
    r, g, b = rgb
    return (
        int(r + (128 - r) * factor),
        int(g + (128 - g) * factor),
        int(b + (128 - b) * factor),
    )


def is_energy_intensive(rgb: RGBColor) -> bool:
    return max(rgb) > 200 or is_light_color(rgb)


def luminance(rgb: RGBColor) -> float:
    r, g, b = [channel / 255.0 for channel in rgb]
    return 0.2126 * (r**3) + 0.7152 * (g**3) + 0.0722 * (b**3)


def calculate_reduction(before_rgb: RGBColor, after_rgb: RGBColor) -> float:
    initial_lum = luminance(before_rgb)
    sustainable_lum = luminance(after_rgb)
    if initial_lum == 0:
        return 0.0
    reduction = ((initial_lum - sustainable_lum) / initial_lum) * 100
    return round(reduction, 2)


def adjust_gradient_rgb_line(line: str, context: str, details: Optional[list[str]] = None) -> str:
    """Ajusta colores RGB dentro de linear-gradient para reducir intensidad."""
    if "linear-gradient" not in line or "rgb(" not in line:
        return line

    parts = line.split("rgb(")
    rebuilt = [parts[0]]
    for index in range(1, len(parts)):
        rgb_value = parts[index].split(")")[0]
        try:
            rgb = tuple(map(int, rgb_value.split(",")))
        except ValueError:
            rebuilt.append("rgb(" + parts[index])
            continue

        if is_energy_intensive(rgb):
            factor = 0.5 if max(rgb) > 240 else 0.3
            adjusted = reduce_energy_intensity(rgb, factor=factor)
            rebuilt.append(f"{adjusted[0]},{adjusted[1]},{adjusted[2]})".join(parts[index].split(")", 1)))
            if details is not None:
                details.append(f"{context}: rgb({rgb_value}) → {rgb_to_css(adjusted)} (gradiente)")
        else:
            rebuilt.append("rgb(" + parts[index])

    return "".join(rebuilt)


def detect_body_background_rgb(soup) -> RGBColor:
    body = soup.find("body")
    if not body or "style" not in body.attrs:
        return (255, 255, 255)

    styles = parse_inline_styles(body["style"])
    background_value = styles.get("background-color")
    if not background_value:
        return (255, 255, 255)

    parsed_rgb = rgb_string_to_tuple(background_value)
    return parsed_rgb if parsed_rgb else (255, 255, 255)


def extract_hex_colors(text: str) -> Iterable[str]:
    return _HEX_PATTERN.findall(text)
