from __future__ import annotations

from engine.domain.models.token import RootToken

def generate_root_css(root_tokens: dict[str, RootToken]) -> str:
    lines = [":root {"]
    for token in root_tokens.values():
        lines.append(f"  {token.token_id}: {token.value};")
    lines.append("}")
    return "\n".join(lines) + "\n"
