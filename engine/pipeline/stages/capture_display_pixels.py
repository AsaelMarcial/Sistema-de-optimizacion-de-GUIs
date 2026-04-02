from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from engine.adapters.color_service import color_registry
from engine.adapters.utils.screenshot import pixels_to_display_color_records
from engine.domain.models.color import (
    ColorInventoryEntry,
    ColorInventoryModel,
    DisplayPixelFrequenciesModel,
    PixelColorRecord,
    UnmatchedVisualPixelsModel,
)
from engine.domain.models.element import Element
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

_DISPLAY_MATCH_DELTA_E_THRESHOLD = 6.0
_EXCLUDED_TAGS = {"img", "picture", "video", "canvas", "source", "track"}


def _session_ready_for_display(session: Session) -> bool:
    return bool(session.original_screenshot_path.strip())

CONTRACT = StageContract(
    name="capture_display_pixels",
    requires=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("session", Session, validator=_session_ready_for_display),
    ),
    produces=(
        context_value("scheme.display_pixels", DisplayPixelFrequenciesModel),
    ),
)


def _iter_excluded_rects(prototype_structure: PrototypeStructure) -> Iterable[dict[str, int]]:
    for element in prototype_structure:
        if not _should_exclude_from_display_scope(element):
            continue
        yield {
            "left": int(element.left),
            "top": int(element.top),
            "right": int(element.right),
            "bottom": int(element.bottom),
        }


def _should_exclude_from_display_scope(element: Element) -> bool:
    if not element.is_visible:
        return False
    if element.is_out_of_scope:
        return True
    if element.tag_name.lower() in _EXCLUDED_TAGS:
        return True
    return bool(element.related_media)


def _match_inventory_entry(
    record: PixelColorRecord,
    colors_inventory: ColorInventoryModel,
) -> ColorInventoryEntry | None:
    exact_entry = colors_inventory.entry_by_value(color_registry.format_color(record.color, "hex"))
    if exact_entry is not None:
        return exact_entry

    best_entry: ColorInventoryEntry | None = None
    best_distance: float | None = None
    for entry in colors_inventory:
        distance = color_registry.delta_e_distance(record.color, entry.rgb, method="2000")
        if distance <= _DISPLAY_MATCH_DELTA_E_THRESHOLD and (
            best_distance is None or distance < best_distance
        ):
            best_entry = entry
            best_distance = distance
    return best_entry


def _build_display_frequencies(
    colors_inventory: ColorInventoryModel,
    display_records: list[PixelColorRecord],
) -> DisplayPixelFrequenciesModel:
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
    for entry in colors_inventory:
        pixel_count = matched_counts.get(entry.color_id, 0)
        pixel_percentage = round((pixel_count / total_pixels) * 100, 4) if total_pixels else 0.0
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
    return DisplayPixelFrequenciesModel(
        matched_inventory_colors=PixelColorRecord.build_many(matched_rows),
        unmatched_visual_pixels=unmatched_summary,
        total_pixels_considered=total_pixels,
    )


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    session = context.get("session")
    prototype_structure = context.get("prototype_structure")
    colors_inventory = prototype_structure.build_color_inventory(
        css_overview=session.original_css_overview,
    )
    screenshot_path = session.original_screenshot_path
    context.trace.add_stage_event(CONTRACT.name, "start")
    excluded_rects = tuple(_iter_excluded_rects(prototype_structure))
    display_records = pixels_to_display_color_records(
        screenshot_path,
        excluded_rects=excluded_rects,
    )
    display_frequencies = _build_display_frequencies(
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

    context.set("scheme.display_pixels", display_frequencies)

    context.trace.add_step(
        "scheme.display_pixels_captured",
        {
            "display_color_count": len(display_records),
            "matched_inventory_colors": len(display_frequencies),
            "unmatched_visual_pixels": display_frequencies.unmatched_visual_pixels.count,
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "display_color_count": len(display_records),
            "matched_inventory_colors": len(display_frequencies),
        },
    )
    return context
