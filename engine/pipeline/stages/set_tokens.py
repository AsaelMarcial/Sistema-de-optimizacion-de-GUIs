from __future__ import annotations

from engine.adapters.utils.io import save_json
from engine.domain.models.inventory_graph import InventoryGraphModel
from engine.domain.models.palette import ColorSchemeArtifactModel
from engine.domain.models.token import TokenInventoryModel
from engine.domain.utils.tokenization import build_token_inventory
from engine.pipeline.artifact_serializers import (
    build_inventory_graph_artifact,
    build_token_inventory_artifact,
)
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="set_tokens",
    requires=(
        context_value("inventory.graph", InventoryGraphModel),
        context_value("scheme.color_scheme", ColorSchemeArtifactModel),
        context_value(
            "session.output.paths.tokens_original_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.inventory_graph_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
    ),
    produces=(
        context_value("token.inventory", TokenInventoryModel),
        context_value("inventory.graph", InventoryGraphModel),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    color_scheme = context.get("scheme.color_scheme")
    inventory_graph = context.get("inventory.graph")
    context.trace.add_stage_event(CONTRACT.name, "start")
    token_inventory = build_token_inventory(inventory_graph, color_scheme)
    token_graph = inventory_graph.bind_inventories(
        elements=inventory_graph.elements,
        styles=inventory_graph.styles,
        colors=inventory_graph.colors,
        palettes=inventory_graph.palettes,
        tokens=token_inventory,
    )
    context.set("token.inventory", token_inventory)
    context.set("inventory.graph", token_graph)
    save_json(
        context.get("session.output.paths.tokens_original_json"),
        build_token_inventory_artifact(token_inventory),
        indent=4,
    )
    save_json(
        context.get("session.output.paths.inventory_graph_json"),
        build_inventory_graph_artifact(
            token_graph,
            css_overview=(
                context.get("session.artifacts.original.css_overview")
                if context.has("session.artifacts.original.css_overview")
                else None
            ),
            contrast_report=(
                context.get("inventory.contrast_report")
                if context.has("inventory.contrast_report")
                else None
            ),
            effect_color_report=(
                context.get("inventory.effect_color_report")
                if context.has("inventory.effect_color_report")
                else None
            ),
            display_frequencies=(
                context.get("session.artifacts.original.pixel_frequencies_display")
                if context.has("session.artifacts.original.pixel_frequencies_display")
                else None
            ),
            raw_pixel_frequencies=(
                context.get("session.artifacts.original.pixel_frequencies_raw")
                if context.has("session.artifacts.original.pixel_frequencies_raw")
                else None
            ),
            color_scheme=color_scheme,
        ),
        indent=4,
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "token_count": len(token_inventory),
            "graph_root_count": len(token_graph.root_ids),
            "tokenized_element_count": len(token_graph.element_to_token_ids),
        },
    )
    return context
