from __future__ import annotations

from engine.domain.models.color import build_inventory_from_scheme_colors
from engine.domain.models.palette import CorePalettesModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.token import TokenInventoryModel
from engine.domain.utils.tokenization import build_token_inventory
from engine.domain.utils.token_graph import TokenGraph
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="set_tokens",
    requires=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("scheme.colors", tuple),
        context_value("scheme.tonal_palettes", CorePalettesModel),
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

    tonal_palettes = context.get("scheme.tonal_palettes")
    inventory_graph = _build_canonical_graph(context)
    context.trace.add_stage_event(CONTRACT.name, "start")
    token_inventory = build_token_inventory(inventory_graph, tonal_palettes)
    context.set("token.inventory", token_inventory)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "token_count": len(token_inventory),
            "graph_root_count": len(inventory_graph.root_ids),
        },
    )
    return context
