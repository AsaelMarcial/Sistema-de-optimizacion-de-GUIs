from __future__ import annotations

from engine.domain.models.color import build_inventory_from_scheme_colors
from engine.domain.models.palette import CorePalettesModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.token import TokenInventoryModel
from engine.domain.utils.token_graph import TokenGraph
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
    produces=(context_value("token.inventory", TokenInventoryModel),),
)


def _build_canonical_graph(
    context: PipelineContext,
    *,
    tokens: TokenInventoryModel | None = None,
) -> TokenGraph:
    return TokenGraph.build_from_canonical(
        context.get("prototype_structure"),
        styles=(),
        colors=build_inventory_from_scheme_colors(tuple(context.get("scheme.colors"))),
        palettes=tuple(context.get("scheme.tonal_palettes")),
        tokens=tokens,
    )


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    token_inventory = context.get("token.inventory")
    inventory_graph = _build_canonical_graph(context)
    context.trace.add_stage_event(CONTRACT.name, "start")
    validated_inventory = apply_token_rules(token_inventory, inventory_graph)
    context.set("token.inventory", validated_inventory)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "token_count": len(validated_inventory),
            "failed_tokens": len([token for token in validated_inventory if token.has_failed_validations]),
            "tokenized_element_count": len(
                {
                    element_id
                    for token in validated_inventory
                    for element_id in token.assigned_element_ids
                    if str(element_id).strip()
                }
            ),
        },
    )
    return context
