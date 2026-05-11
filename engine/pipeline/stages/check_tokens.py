from __future__ import annotations

from engine.domain.models.color import ColorCatalog
from engine.domain.models.palette import CorePalettesModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.token import TokenInventoryModel
from engine.domain.utils.tokenization import apply_token_assignments
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.token_rules import apply_token_rules

CONTRACT = StageContract(
    name="check_tokens",
    requires=(
        context_value(K.PROTOTYPE_STRUCTURE, PrototypeStructure),
        context_value(K.COLOR_CATALOG, ColorCatalog),
        context_value(K.SCHEME_TONAL_PALETTES, CorePalettesModel),
        context_value(K.TOKEN_INVENTORY, TokenInventoryModel),
    ),
    produces=(
        context_value(K.PROTOTYPE_STRUCTURE, PrototypeStructure),
        context_value(K.COLOR_CATALOG, ColorCatalog),
        context_value(K.TOKEN_INVENTORY, TokenInventoryModel),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    prototype_structure = context.get(K.PROTOTYPE_STRUCTURE)
    colors = context.get(K.COLOR_CATALOG)
    token_inventory = context.get(K.TOKEN_INVENTORY)
    tonal_palettes = context.get(K.SCHEME_TONAL_PALETTES)
    context.trace.add_stage_event(CONTRACT.name, "start")
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
    context.set(K.PROTOTYPE_STRUCTURE, prototype_structure)
    context.set(K.COLOR_CATALOG, colors)
    context.set(K.TOKEN_INVENTORY, validated_inventory)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "token_count": len(validated_inventory),
            "failed_tokens": len([token for token in validated_inventory if token.has_failed_validations]),
            "tokenized_element_count": len(
                {
                    element.node_id
                    for element in prototype_structure
                    if element.token_ids
                }
            ),
        },
    )
    return context
