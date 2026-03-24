from __future__ import annotations

import re
from collections.abc import Iterable

_HEX_PATTERN = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}")


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
    return _HEX_PATTERN.findall(text)
