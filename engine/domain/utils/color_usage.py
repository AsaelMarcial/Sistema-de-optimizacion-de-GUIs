from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from engine.adapters.color_service import color_registry
from engine.domain.enums.scope.css_properties import CSS_PROPERTIES_BY_ID
from engine.domain.models.color import Color, ColorCatalog
from engine.domain.models.prototype_structure import PrototypeStructure

_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_FUNCTION_COLOR_RE = re.compile(r"(?:rgba?|hsla?)\([^)]+\)", re.IGNORECASE)

_COMPOSITE_COLOR_PROPERTIES = frozenset(
    {
        "background",
        "border",
        "caret",
        "column-rule",
        "outline",
        "text-decoration",
        "text-emphasis",
    }
)
_PURE_COLOR_PROPERTIES = frozenset(
    property_name
    for property_name, spec in CSS_PROPERTIES_BY_ID.items()
    if spec.color_role is not None and property_name not in _COMPOSITE_COLOR_PROPERTIES
)
_COLOR_VALUE_PROPERTIES = _PURE_COLOR_PROPERTIES | _COMPOSITE_COLOR_PROPERTIES
def build_color_usage_catalog(
    prototype_structure: PrototypeStructure,
    *,
    existing_inventory: ColorCatalog | None = None,
) -> ColorCatalog:
    """Derive a ColorCatalog projection from structural state.

    This utility does not own pipeline state and does not create a parallel
    source of truth. It derives color usage from PrototypeStructure and returns
    ColorCatalog because that model lives in engine.domain.models.color.
    """

    payloads: list[dict[str, Any]] = []
    for element in prototype_structure:
        seen_signatures: set[tuple[str, str]] = set()
        for property_model in element.properties:
            for color_value in _extract_palette_colors(property_model.name, property_model.value):
                signature = (property_model.name, color_value)
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)
                existing_entry = (
                    existing_inventory.entry_by_value(color_value)
                    if existing_inventory is not None
                    else None
                )
                payload: dict[str, Any] = {
                    "value": color_value,
                    "usage_count": 1,
                    "node_ids": [element.node_id],
                    "usage": [
                        {
                            "tag": element.tag_name,
                            "property": property_model.name,
                            "count": 1,
                        }
                    ],
                }
                preserved_entry = existing_entry
                if property_model.color_id is not None and existing_inventory is not None:
                    preserved_entry = (
                        existing_inventory.entry_by_id(property_model.color_id)
                        or existing_entry
                    )
                if property_model.color_id is not None:
                    payload["color_id"] = property_model.color_id
                elif preserved_entry is not None:
                    payload["color_id"] = preserved_entry.color_id
                payloads.append(payload)

    inventory = ColorCatalog.build(payloads)
    if existing_inventory is None:
        return inventory

    merged_entries: list[Color] = []
    for entry in inventory:
        existing_entry = existing_inventory.entry_by_id(entry.color_id) or existing_inventory.entry_by_value(
            entry.value
        )
        if existing_entry is None:
            merged_entries.append(entry)
            continue
        merged_entries.append(
            replace(
                entry,
                pixel_count=existing_entry.pixel_count,
                pixel_percentage=existing_entry.pixel_percentage,
                mapped_palette_id=existing_entry.mapped_palette_id,
                mapped_tone=existing_entry.mapped_tone,
                mapped_tone_rgb=existing_entry.mapped_tone_rgb,
                mapped_tone_distance=existing_entry.mapped_tone_distance,
            )
        )
    return ColorCatalog.build(merged_entries)


def _normalize_color_token(value: str) -> str:
    return color_registry.normalize_css_color_token(value)


def _extract_palette_colors(property_name: str, value: str) -> tuple[str, ...]:
    if property_name not in _COLOR_VALUE_PROPERTIES:
        return ()

    if property_name in _PURE_COLOR_PROPERTIES:
        normalized = _normalize_color_token(value)
        return () if not normalized or normalized == "transparent" else (normalized,)

    colors: list[str] = []
    for token in _HEX_COLOR_RE.findall(value):
        normalized = _normalize_color_token(token)
        if normalized and normalized != "transparent" and normalized not in colors:
            colors.append(normalized)
    for token in _FUNCTION_COLOR_RE.findall(value):
        normalized = _normalize_color_token(token)
        if normalized and normalized != "transparent" and normalized not in colors:
            colors.append(normalized)
    return tuple(colors)
