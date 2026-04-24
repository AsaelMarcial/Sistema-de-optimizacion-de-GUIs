from __future__ import annotations

from engine.domain.models.palette import CorePalettesModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.token import TokenInventoryModel
from engine.domain.utils.tokenization import apply_token_assignments
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.token_rules import apply_token_rules

CONTRACT = StageContract(
    name="check_tokens",
    requires=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("scheme.colors", tuple),
        context_value("scheme.tonal_palettes", CorePalettesModel),
        context_value("token.inventory", TokenInventoryModel),
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
    token_inventory = context.get("token.inventory")
    tonal_palettes = context.get("scheme.tonal_palettes")
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
    context.set("prototype_structure", prototype_structure)
    context.set("scheme.colors", colors)
    context.set("token.inventory", validated_inventory)
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
