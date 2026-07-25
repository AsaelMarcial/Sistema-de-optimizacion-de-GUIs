from __future__ import annotations

from engine.domain.models.token import PropertyToken, RootToken


def generate_root_css(
    root_tokens: dict[str, RootToken],
    property_tokens: dict[str, PropertyToken] | None = None,
) -> str:
    lines = [":root {"]
    lines.append("  color-scheme: dark;")
    for token in root_tokens.values():
        lines.append(f"  {token.token_id}: {token.value};")
    lines.append("}")
    if property_tokens:
        lines.append("")
        lines.append('[data-theme="glow"] {')
        for token in property_tokens.values():
            lines.append(f"  {token.token_id}: {token.glow_theme_value};")
        lines.append("}")
        lines.append("")
        lines.append('[data-theme="original"] {')
        for token in property_tokens.values():
            lines.append(f"  {token.token_id}: {token.original_theme_value};")
        lines.append("}")
    return "\n".join(lines) + "\n"
