from __future__ import annotations

from engine.adapters.utils.io import save_json
from engine.domain.models.inventory_graph import InventoryGraphModel
from engine.domain.models.token import TokenInventoryModel
from engine.pipeline.artifact_serializers import (
    build_inventory_graph_artifact,
    build_token_inventory_artifact,
)
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.token_rules import apply_token_rules

CONTRACT = StageContract(
    name="check_tokens",
    requires=(
        context_value("token.inventory", TokenInventoryModel),
        context_value("inventory.graph", InventoryGraphModel),
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

    token_inventory = context.get("token.inventory")
    inventory_graph = context.get("inventory.graph")
    context.trace.add_stage_event(CONTRACT.name, "start")
    validated_inventory = apply_token_rules(token_inventory, inventory_graph)
    validated_graph = inventory_graph.bind_inventories(
        elements=inventory_graph.elements,
        styles=inventory_graph.styles,
        colors=inventory_graph.colors,
        palettes=inventory_graph.palettes,
        tokens=validated_inventory,
    )
    context.set("token.inventory", validated_inventory)
    context.set("inventory.graph", validated_graph)
    save_json(
        context.get("session.output.paths.tokens_original_json"),
        build_token_inventory_artifact(validated_inventory),
        indent=4,
    )
    save_json(
        context.get("session.output.paths.inventory_graph_json"),
        build_inventory_graph_artifact(
            validated_graph,
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
        ),
        indent=4,
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "token_count": len(validated_inventory),
            "failed_tokens": len([token for token in validated_inventory if token.has_failed_validations]),
            "tokenized_element_count": len(validated_graph.element_to_token_ids),
        },
    )
    return context
