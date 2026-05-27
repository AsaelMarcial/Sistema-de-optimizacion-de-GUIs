from __future__ import annotations

from engine.domain.models.color import Color, ColorCatalog
from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.token import TokenInventoryModel
from engine.domain.utils.tokenization import apply_token_assignments, build_token_inventory
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="set_tokens",
    requires=(
        context_value(K.PROTOTYPE_STRUCTURE, PrototypeStructure),
        context_value(K.COLOR_CATALOG, ColorCatalog),
        context_value(K.SCHEME_TONAL_PALETTES, ColorScheme),
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
    tonal_palettes = context.get(K.SCHEME_TONAL_PALETTES)
    context.trace.add_stage_event(CONTRACT.name, "start")
    token_inventory = build_token_inventory(prototype_structure, colors, tonal_palettes)
    prototype_structure, colors = apply_token_assignments(
        prototype_structure,
        colors,
        token_inventory,
    )
    context.set(K.PROTOTYPE_STRUCTURE, prototype_structure)
    context.set(K.COLOR_CATALOG, colors)
    context.set(K.TOKEN_INVENTORY, token_inventory)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "token_count": len(token_inventory),
            "tokenized_color_count": len([color for color in colors if isinstance(color, Color) and color.token]),
            "tokenized_element_count": len([element for element in prototype_structure if element.token_ids]),
        },
    )
    return context

