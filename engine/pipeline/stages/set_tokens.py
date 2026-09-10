from __future__ import annotations

from engine.domain.models.color import Color
from engine.domain.utils.tokenization import apply_token_assignments, build_token_inventory
from engine.pipeline.context import PipelineContext


def set_tokens(context: PipelineContext) -> None:
    prototype_structure = context.prototype_structure
    colors = context.color_catalog
    tonal_palettes = context.scheme_tonal_palettes
    token_inventory = build_token_inventory(prototype_structure, colors, tonal_palettes)
    prototype_structure, colors = apply_token_assignments(
        prototype_structure,
        colors,
        token_inventory,
    )
    context.prototype_structure = prototype_structure
    context.color_catalog = colors
    context.token_inventory = token_inventory
    print({
        "set_tokens.complete": {
            "token_count": len(token_inventory),
            "tokenized_color_count": len([color for color in colors if isinstance(color, Color) and color.token]),
            "tokenized_element_count": len([element for element in prototype_structure if element.token_ids]),
        }
    })
