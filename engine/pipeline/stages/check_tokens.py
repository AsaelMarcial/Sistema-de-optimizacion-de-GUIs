from __future__ import annotations

from engine.domain.utils.tokenization import apply_token_assignments
from engine.pipeline.context import PipelineContext
from engine.validators.token_rules import apply_token_rules


def check_tokens(context: PipelineContext) -> None:
    prototype_structure = context.prototype_structure
    colors = context.color_catalog
    token_inventory = context.token_inventory
    tonal_palettes = context.scheme_tonal_palettes
    validated_inventory = apply_token_rules(
        token_inventory,
        prototype_structure,
        colors,
        tuple(tonal_palettes),
    )
    prototype_structure, colors = apply_token_assignments(
        prototype_structure,
        colors,
        validated_inventory,
    )
    context.prototype_structure = prototype_structure
    context.color_catalog = colors
    context.token_inventory = validated_inventory
    print({
        "check_tokens.complete": {
            "token_count": len(validated_inventory),
            "failed_tokens": len([token for token in validated_inventory if token.has_failed_validations]),
            "tokenized_element_count": len(
                {
                    element.node_id
                    for element in prototype_structure
                    if element.token_ids
                }
            ),
        }
    })
