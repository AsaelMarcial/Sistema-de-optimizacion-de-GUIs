from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping, Sequence

from engine.domain.models.color import ColorInventoryModel, DisplayPixelFrequenciesModel
from engine.domain.models.contrast import ContrastReportModel
from engine.domain.models.effect_color import EffectColorReportModel
from engine.domain.models.element import ElementInventoryModel
from engine.domain.models.inventory_graph import InventoryGraphModel
from engine.domain.models.palette import ColorSchemeArtifactModel
from engine.domain.models.style import StyleInventoryModel
from engine.domain.models.token import TokenInventoryModel


def build_elements_inventory_artifact(
    elements_inventory: ElementInventoryModel,
) -> dict[str, Any]:
    return {
        "tree": list(elements_inventory.to_tree()),
    }


def build_styles_inventory_artifact(
    styles_inventory: StyleInventoryModel,
) -> dict[str, Any]:
    entries_by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in styles_inventory.to_dict():
        kind = str(entry.get("kind") or "embedded")
        entries_by_kind[kind].append(entry)
    ordered_kinds = ("inline", "embedded", "external", "inherited", "user-agent")
    payload: dict[str, list[dict[str, Any]]] = {}
    for kind in ordered_kinds:
        if entries_by_kind.get(kind):
            payload[kind] = entries_by_kind[kind]
    for kind in sorted(entries_by_kind):
        if kind not in payload:
            payload[kind] = entries_by_kind[kind]
    return payload


def build_colors_inventory_artifact(
    colors_inventory: ColorInventoryModel,
) -> dict[str, Any]:
    return {"entries": colors_inventory.to_dict()}


def build_token_inventory_artifact(
    token_inventory: TokenInventoryModel,
) -> dict[str, Any]:
    return token_inventory.to_dict()


def build_inventory_graph_artifact(
    inventory_graph: InventoryGraphModel,
    *,
    css_overview: Mapping[str, Any] | None = None,
    contrast_report: ContrastReportModel | None = None,
    effect_color_report: EffectColorReportModel | None = None,
    display_frequencies: DisplayPixelFrequenciesModel | None = None,
    raw_pixel_frequencies: Sequence[Mapping[str, Any]] | None = None,
    color_scheme: ColorSchemeArtifactModel | None = None,
) -> dict[str, Any]:
    summary = _build_inventory_graph_summary(
        inventory_graph,
        css_overview=css_overview,
        contrast_report=contrast_report,
        display_frequencies=display_frequencies,
        raw_pixel_frequencies=raw_pixel_frequencies,
    )
    payload = inventory_graph.to_artifact_dict()
    payload.update(
        {
            "schema_version": "3.0",
            "generated_from": (
                "inventory.graph.tokens"
                if inventory_graph.token_ids
                else "inventory.graph.base"
            ),
            "summary": summary,
        }
    )
    return payload


def build_display_pixel_artifact(
    display_frequencies: DisplayPixelFrequenciesModel,
) -> dict[str, Any]:
    return display_frequencies.to_dict()


def _build_raw_pixel_summary(
    raw_pixel_frequencies: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    return {
        "pixel_count": sum(int(item.get("count") or 0) for item in raw_pixel_frequencies),
        "distinct_color_count": sum(1 for item in raw_pixel_frequencies if item.get("color") is not None),
    }


def _build_inventory_graph_summary(
    inventory_graph: InventoryGraphModel,
    *,
    css_overview: Mapping[str, Any] | None = None,
    contrast_report: ContrastReportModel | None = None,
    display_frequencies: DisplayPixelFrequenciesModel | None = None,
    raw_pixel_frequencies: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    css_summary = dict((css_overview or {}).get("summary") or {})
    visible_entries = inventory_graph.elements.visible_entries()
    text_entries = tuple(
        entry
        for entry in inventory_graph.elements
        if entry.flags.is_text_node or bool(str(entry.text or "").strip())
    )
    declaration_entries = tuple(
        declaration
        for style_entry in inventory_graph.styles
        for declaration in style_entry.declarations
    )
    computed_styles = tuple(
        style_payload
        for element_entry in inventory_graph.elements
        for _, style_payload in element_entry.iter_computed_styles()
    )
    exact_match_count = sum(
        1
        for style_payload in computed_styles
        if getattr(style_payload.resolution_status, "value", style_payload.resolution_status)
        == "exact_match"
    )
    ambiguous_match_count = sum(
        1
        for style_payload in computed_styles
        if getattr(style_payload.resolution_status, "value", style_payload.resolution_status)
        == "ambiguous_match"
    )
    unresolved_match_count = sum(
        1
        for style_payload in computed_styles
        if getattr(style_payload.resolution_status, "value", style_payload.resolution_status)
        == "unresolved"
    )
    display_total = display_frequencies.total_pixels_considered if display_frequencies is not None else 0
    matched_pixels = (
        sum(record.count for record in display_frequencies.matched_inventory_colors)
        if display_frequencies is not None
        else 0
    )
    unmatched_pixels = (
        display_frequencies.unmatched_visual_pixels.count if display_frequencies is not None else 0
    )
    raw_summary = _build_raw_pixel_summary(raw_pixel_frequencies or ())
    token_entries = tuple(inventory_graph.tokens)
    foundation_token_count = sum(1 for token in token_entries if token.is_foundation)
    semantic_token_count = sum(1 for token in token_entries if token.is_semantic)
    component_token_count = sum(1 for token in token_entries if token.is_component)
    validated_token_count = sum(
        1
        for token in token_entries
        if getattr(getattr(token, "state", None), "value", getattr(token, "state", None))
        in {"validated", "applied"}
    )
    failed_token_count = sum(
        1 for token in token_entries if getattr(token, "has_failed_validations", False)
    )

    return {
        "element_count": len(inventory_graph.element_ids),
        "visible_element_count": len(visible_entries),
        "text_element_count": len(text_entries),
        "root_count": len(inventory_graph.root_ids),
        "leaf_element_count": sum(1 for entry in inventory_graph.elements if entry.flags.is_leaf),
        "out_of_scope_element_count": sum(
            1 for entry in inventory_graph.elements if entry.flags.is_out_of_scope
        ),
        "stacking_context_count": sum(
            1 for entry in inventory_graph.elements if entry.flags.is_stacking_context
        ),
        "style_count": len(inventory_graph.style_ids),
        "declaration_count": len(declaration_entries),
        "used_declaration_count": sum(
            1
            for declaration in declaration_entries
            if getattr(declaration.usage_status, "value", declaration.usage_status) == "used"
        ),
        "computed_style_count": len(computed_styles),
        "exact_match_count": exact_match_count,
        "ambiguous_match_count": ambiguous_match_count,
        "unresolved_match_count": unresolved_match_count,
        "color_count": len(inventory_graph.color_ids),
        "mapped_color_count": sum(
            1 for color_entry in inventory_graph.colors if color_entry.mapped_palette_id is not None
        ),
        "confirmed_color_count": sum(
            1 for color_entry in inventory_graph.colors if int(color_entry.display_pixel_count) > 0
        ),
        "palette_count": len(inventory_graph.palettes),
        "chromatic_palette_count": sum(
            1
            for palette in inventory_graph.palettes
            if getattr(palette.palette_type, "value", palette.palette_type) == "chromatic"
        ),
        "token_count": len(inventory_graph.token_ids),
        "foundation_token_count": foundation_token_count,
        "semantic_token_count": semantic_token_count,
        "component_token_count": component_token_count,
        "validated_token_count": validated_token_count,
        "failed_token_count": failed_token_count,
        "tokenized_element_count": len(inventory_graph.element_to_token_ids),
        "tokenized_style_ref_count": len(inventory_graph.style_ref_to_token_ids),
        "tokenized_color_count": len(inventory_graph.color_to_token_ids),
        "tokenized_palette_tone_count": len(inventory_graph.palette_tone_to_token_ids),
        "pixel_count": raw_summary["pixel_count"] or display_total,
        "raw_pixel_count": raw_summary["pixel_count"],
        "raw_distinct_color_count": raw_summary["distinct_color_count"],
        "display_pixel_count": display_total,
        "matched_inventory_pixel_count": matched_pixels,
        "unmatched_visual_pixel_count": unmatched_pixels,
        "unmatched_visual_cluster_count": (
            display_frequencies.unmatched_visual_pixels.distinct_clusters
            if display_frequencies is not None
            else 0
        ),
        "inline_style_count": int(css_summary.get("inline_style_count") or 0),
        "stylesheet_count": int(css_summary.get("stylesheet_count") or 0),
        "external_stylesheet_count": int(css_summary.get("external_stylesheet_count") or 0),
        "inline_stylesheet_count": int(css_summary.get("inline_stylesheet_count") or 0),
        "media_query_count": int(css_summary.get("media_query_count") or 0),
        "contrast_issue_count": (
            len(contrast_report)
            if contrast_report is not None
            else int(css_summary.get("contrast_issue_count") or 0)
        ),
        "unused_declaration_count": int(css_summary.get("unused_declaration_count") or 0),
    }


def _build_inventory_graph_relations(
    inventory_graph: InventoryGraphModel,
) -> dict[str, Any]:
    return dict(inventory_graph.to_artifact_dict().get("relations") or {})
