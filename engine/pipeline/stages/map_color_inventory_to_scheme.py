from __future__ import annotations

from engine.adapters.utils.io import save_json
from engine.domain.models.color import ColorInventoryModel
from engine.domain.models.palette import ColorSchemeArtifactModel
from engine.pipeline.artifact_serializers import build_colors_inventory_artifact
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="map_color_inventory_to_scheme",
    requires=(
        context_value("color.inventory", ColorInventoryModel),
        context_value("scheme.color_scheme", ColorSchemeArtifactModel),
        context_value(
            "session.output.paths.original.colors_inventory_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
    ),
    produces=(context_value("color.inventory", ColorInventoryModel),),
)


def _map_color_inventory(
    colors_inventory: ColorInventoryModel,
    color_scheme_model: ColorSchemeArtifactModel,
) -> ColorInventoryModel:
    semantic_colors_by_id = {
        color.color_id: color
        for color in color_scheme_model.semantic_colors
    }
    mapped_entries = []
    for entry in colors_inventory:
        semantic_color = semantic_colors_by_id.get(entry.color_id)
        if semantic_color is None or semantic_color.mapped_palette_id is None:
            mapped_entries.append(entry)
            continue
        mapped_entries.append(
            entry.with_palette_mapping(
                palette_id=semantic_color.mapped_palette_id,
                tone=semantic_color.mapped_tone or 0,
                tone_rgb=semantic_color.mapped_tone_rgb or entry.rgb,
                tone_distance=semantic_color.mapped_tone_distance or 0.0,
            )
        )
    return ColorInventoryModel.build(mapped_entries)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    colors_inventory = context.get("color.inventory")
    if not len(colors_inventory):
        return context

    context.trace.add_stage_event(CONTRACT.name, "start")
    mapped_inventory = _map_color_inventory(
        colors_inventory,
        context.get("scheme.color_scheme"),
    )
    context.set("color.inventory", mapped_inventory)
    save_json(
        context.get("session.output.paths.original.colors_inventory_json"),
        build_colors_inventory_artifact(mapped_inventory),
        indent=4,
    )
    context.trace.add_step(
        "inventories.colors_mapped_to_scheme",
        {
            "mapped_colors": len(
                [entry for entry in mapped_inventory if entry.mapped_palette_id is not None]
            ),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "mapped_colors": len(
                [entry for entry in mapped_inventory if entry.mapped_palette_id is not None]
            ),
        },
    )
    return context
