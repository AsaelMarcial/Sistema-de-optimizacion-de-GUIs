from __future__ import annotations

from collections.abc import Iterable

from engine.adapters.color_service import color_registry


def parse_inline_styles(style_str: str) -> dict[str, str]:
    styles: dict[str, str] = {}
    for item in style_str.split(";"):
        if ":" in item:
            key, value = item.split(":", 1)
            styles[key.strip()] = value.strip()
    return styles


def reconstruct_inline_style(styles_dict: dict[str, str]) -> str:
    return "; ".join(f"{key}: {value}" for key, value in styles_dict.items())


def extract_hex_colors(text: str) -> Iterable[str]:
    return tuple(
        color_registry.format_color(token, "hex")
        for _start, _end, token in color_registry.find_matches(text)
    )
