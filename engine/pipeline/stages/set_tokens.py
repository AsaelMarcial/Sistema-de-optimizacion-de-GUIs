from __future__ import annotations

from engine.domain.models.color import Color
from engine.domain.models.palette import CorePalettesModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.token import TokenInventoryModel
from engine.domain.utils.tokenization import apply_token_assignments, build_token_inventory
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="set_tokens",
    requires=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("scheme.colors", tuple),
        context_value("scheme.tonal_palettes", CorePalettesModel),
    ),
    produces=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("scheme.colors", tuple),
        context_value("token.inventory", TokenInventoryModel),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    prototype_structure = context.get("prototype_structure")
    colors = tuple(context.get("scheme.colors"))
    tonal_palettes = context.get("scheme.tonal_palettes")
    context.trace.add_stage_event(CONTRACT.name, "start")
    token_inventory = build_token_inventory(prototype_structure, colors, tonal_palettes)
    prototype_structure, colors = apply_token_assignments(
        prototype_structure,
        colors,
        token_inventory,
    )
    context.set("prototype_structure", prototype_structure)
    context.set("scheme.colors", colors)
    context.set("token.inventory", token_inventory)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "token_count": len(token_inventory),
            "tokenized_color_count": len([color for color in colors if isinstance(color, Color) and color.token_ids]),
            "tokenized_element_count": len([element for element in prototype_structure if element.token_ids]),
        },
    )
    return context
