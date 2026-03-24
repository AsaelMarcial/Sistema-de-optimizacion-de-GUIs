from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from engine.adapters.utils.io import save_json
from engine.adapters.utils.screenshot import pixels_to_display_color_records
from engine.domain.models.color import (
    ColorInventoryEntry,
    ColorInventoryModel,
    DisplayPixelFrequenciesModel,
    PixelColorRecord,
    UnmatchedVisualPixelsModel,
)
from engine.domain.models.element import ElementInventoryEntry, ElementInventoryModel
from engine.domain.utils.coloraide import color_to_hex, delta_e_distance
from engine.pipeline.artifact_serializers import (
    build_colors_inventory_artifact,
    build_display_pixel_artifact,
)
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

_DISPLAY_MATCH_DELTA_E_THRESHOLD = 6.0
_EXCLUDED_TAGS = {"img", "picture", "video", "canvas", "source", "track"}

CONTRACT = StageContract(
    name="enrich_color_inventory",
    requires=(
        context_value("elements.inventory", ElementInventoryModel),
        context_value("color.inventory", ColorInventoryModel),
        context_value("session.artifacts.original.screenshot", str, validator=lambda value: bool(value.strip())),
        context_value(
            "session.output.paths.original.colors_inventory_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.original.pixel_frequencies_display_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
    ),
    produces=(
        context_value("color.inventory", ColorInventoryModel),
        context_value("session.artifacts.original.pixel_frequencies_display", DisplayPixelFrequenciesModel),
    ),
)


def _iter_excluded_rects(elements_inventory: ElementInventoryModel) -> Iterable[dict[str, int]]:
    for element in elements_inventory:
        if not _should_exclude_from_display_scope(element):
            continue
        bounds = element.layout.absolute_bounds
        yield {
            "left": int(bounds.left),
            "top": int(bounds.top),
            "right": int(bounds.right),
            "bottom": int(bounds.bottom),
        }


def _should_exclude_from_display_scope(element: ElementInventoryEntry) -> bool:
    if not element.flags.is_visible:
        return False
    if element.flags.is_out_of_scope:
        return True
    if element.identity.tag.lower() in _EXCLUDED_TAGS:
        return True
    return bool(element.identity.related_media)


def _match_inventory_entry(
    record: PixelColorRecord,
    colors_inventory: ColorInventoryModel,
) -> ColorInventoryEntry | None:
    exact_entry = colors_inventory.entry_by_value(color_to_hex(record.color))
    if exact_entry is not None:
        return exact_entry

    best_entry: ColorInventoryEntry | None = None
    best_distance: float | None = None
    for entry in colors_inventory:
        distance = delta_e_distance(record.color, entry.rgb, method="2000")
        if distance <= _DISPLAY_MATCH_DELTA_E_THRESHOLD and (
            best_distance is None or distance < best_distance
        ):
            best_entry = entry
            best_distance = distance
    return best_entry


def _enrich_inventory(
    colors_inventory: ColorInventoryModel,
    display_records: list[PixelColorRecord],
) -> tuple[ColorInventoryModel, DisplayPixelFrequenciesModel]:
    total_pixels = sum(record.count for record in display_records)
    matched_counts: dict[str, int] = defaultdict(int)
    matched_cluster_flags: dict[str, bool] = defaultdict(bool)
    matched_cluster_count: dict[str, int] = defaultdict(int)
    unmatched_pixels = 0
    unmatched_clusters = 0

    for record in display_records:
        matched_entry = _match_inventory_entry(record, colors_inventory)
        clustered = bool((record.metadata or {}).get("clustered"))
        if matched_entry is None:
            unmatched_pixels += record.count
            unmatched_clusters += 1
            continue

        matched_counts[matched_entry.color_id] += record.count
        matched_cluster_flags[matched_entry.color_id] = (
            matched_cluster_flags[matched_entry.color_id] or clustered
        )
        matched_cluster_count[matched_entry.color_id] += 1

    matched_rows: list[dict[str, Any]] = []
    enriched_entries: list[ColorInventoryEntry] = []
    for entry in colors_inventory:
        pixel_count = matched_counts.get(entry.color_id, 0)
        pixel_percentage = round((pixel_count / total_pixels) * 100, 4) if total_pixels else 0.0
        enriched_entries.append(
            entry.with_display_evidence(
                pixel_count=pixel_count,
                pixel_percentage=pixel_percentage,
                clustered=matched_cluster_flags.get(entry.color_id, False),
            )
        )
        if pixel_count <= 0:
            continue
        matched_rows.append(
            {
                "color_id": entry.color_id,
                "color": list(entry.rgb),
                "count": pixel_count,
                "percentage": pixel_percentage,
                "source": "display",
                "metadata": {
                    "matched_to_inventory": True,
                    "value": entry.value,
                    "clustered": matched_cluster_flags.get(entry.color_id, False),
                    "matched_cluster_count": matched_cluster_count.get(entry.color_id, 0),
                },
            }
        )

    unmatched_summary = UnmatchedVisualPixelsModel(
        count=unmatched_pixels,
        percentage=round((unmatched_pixels / total_pixels) * 100, 4) if total_pixels else 0.0,
        distinct_clusters=unmatched_clusters,
    )
    matched_rows.sort(
        key=lambda item: (
            -int(item.get("count") or 0),
            str(item.get("color_id") or ""),
        )
    )
    return (
        colors_inventory.with_entries(tuple(enriched_entries)),
        DisplayPixelFrequenciesModel(
            matched_inventory_colors=PixelColorRecord.build_many(matched_rows),
            unmatched_visual_pixels=unmatched_summary,
            total_pixels_considered=total_pixels,
        ),
    )


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    colors_inventory = context.get("color.inventory")
    if not len(colors_inventory):
        context.set(
            "session.artifacts.original.pixel_frequencies_display",
            DisplayPixelFrequenciesModel(),
        )
        return context

    elements_inventory = context.get("elements.inventory")
    screenshot_path = context.get("session.artifacts.original.screenshot")
    context.trace.add_stage_event(CONTRACT.name, "start")
    excluded_rects = tuple(_iter_excluded_rects(elements_inventory))
    display_records = pixels_to_display_color_records(
        screenshot_path,
        excluded_rects=excluded_rects,
    )
    enriched_inventory, display_frequencies = _enrich_inventory(
        colors_inventory,
        display_records,
    )
    display_frequencies = DisplayPixelFrequenciesModel(
        matched_inventory_colors=display_frequencies.matched_inventory_colors,
        unmatched_visual_pixels=display_frequencies.unmatched_visual_pixels,
        total_pixels_considered=display_frequencies.total_pixels_considered,
        excluded_regions_summary={
            "excluded_rect_count": len(excluded_rects),
        },
    )

    context.set("color.inventory", enriched_inventory)
    context.set("session.artifacts.original.pixel_frequencies_display", display_frequencies)
    save_json(
        context.get("session.output.paths.original.pixel_frequencies_display_json"),
        build_display_pixel_artifact(display_frequencies),
        indent=4,
    )
    save_json(
        context.get("session.output.paths.original.colors_inventory_json"),
        build_colors_inventory_artifact(enriched_inventory),
        indent=4,
    )

    context.trace.add_step(
        "inventories.colors_enriched",
        {
            "display_color_count": len(display_records),
            "inventory_color_count": len(enriched_inventory),
            "matched_inventory_colors": len(display_frequencies),
            "unmatched_visual_pixels": display_frequencies.unmatched_visual_pixels.count,
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "display_color_count": len(display_records),
            "inventory_color_count": len(enriched_inventory),
        },
    )
    return context
