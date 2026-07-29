from __future__ import annotations

from engine.domain.models.color_scheme import ColorScheme, Palette
from engine.domain.models.token import PropertyToken


def generate_root_css(palettes: dict[str, Palette]) -> str:
    lines = [":root {"]
    lines.append("  color-scheme: dark;")
    for palette in palettes.values():
        for tone in palette.tones:
            lines.append(f"  {tone.name}: {ColorScheme.serialize_color(tone.color)};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def generate_theme_css(property_tokens: dict[str, PropertyToken]) -> str:
    lines = ['[data-theme="glow"] {']
    for token in property_tokens.values():
        lines.append(f"  {token.token_id}: {token.glow_theme_value};")
    lines.append("}")
    lines.append("")
    lines.append('[data-theme="original"] {')
    for token in property_tokens.values():
        lines.append(f"  {token.token_id}: {token.original_theme_value};")
    lines.append("}")
    return "\n".join(lines) + "\n"
