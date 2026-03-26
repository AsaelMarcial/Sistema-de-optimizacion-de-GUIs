from __future__ import annotations

from engine.adapters.utils.io import save_json
from engine.domain.models.color import ColorInventoryModel, DisplayPixelFrequenciesModel
from engine.domain.models.inventory_graph import InventoryGraphModel
from engine.domain.models.palette import ColorSchemeArtifactModel
from engine.domain.models.style import StyleInventoryModel
from engine.pipeline.artifact_serializers import build_inventory_graph_artifact
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="build_inventory_graph_base",
    requires=(
        context_value("elements.inventory"),
        context_value("style.inventory", StyleInventoryModel),
        context_value("color.inventory", ColorInventoryModel),
        context_value("scheme.color_scheme", ColorSchemeArtifactModel),
        context_value("session.artifacts.original.css_overview", dict),
        context_value(
            "session.artifacts.original.pixel_frequencies_display",
            DisplayPixelFrequenciesModel,
        ),
        context_value(
            "session.output.paths.inventory_graph_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
    ),
    produces=(context_value("inventory.graph", InventoryGraphModel),),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("inventory.graph"):
        return context

    color_scheme = context.get("scheme.color_scheme")
    inventory_graph = InventoryGraphModel.build(
        elements=context.get("elements.inventory"),
        styles=context.get("style.inventory"),
        colors=context.get("color.inventory"),
        palettes=tuple(color_scheme.core_palettes),
    )
    context.trace.add_stage_event(CONTRACT.name, "start")
    context.set("inventory.graph", inventory_graph)
    save_json(
        context.get("session.output.paths.inventory_graph_json"),
        build_inventory_graph_artifact(
            inventory_graph,
            css_overview=context.get("session.artifacts.original.css_overview"),
            display_frequencies=context.get("session.artifacts.original.pixel_frequencies_display"),
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
            "element_count": len(inventory_graph.elements),
            "color_count": len(inventory_graph.colors),
            "palette_count": len(inventory_graph.palettes),
        },
    )
    return context
