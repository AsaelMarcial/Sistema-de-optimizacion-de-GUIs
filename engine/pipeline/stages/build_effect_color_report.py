from __future__ import annotations

import re

from engine.domain.models.color import build_inventory_from_scheme_colors
from engine.domain.models.quality_reports import (
    EffectColorEntry,
    EffectColorReport,
    EffectColorToken,
)
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.adapters.color_service import color_registry
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

_EFFECT_COLOR_PROPERTIES = (
    "background-image",
    "text-shadow",
    "box-shadow",
    "filter",
)
_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_FUNCTION_COLOR_RE = re.compile(r"(?:rgba?|hsla?)\([^)]+\)", re.IGNORECASE)

CONTRACT = StageContract(
    name="build_effect_color_report",
    requires=(
        context_value("prototype_structure", PrototypeStructure),
        context_value("scheme.colors", tuple),
    ),
    produces=(context_value("derived.effect_color_report", EffectColorReport),),
)


def _extract_effect_colors(value: str) -> tuple[str, ...]:
    normalized = str(value or "").strip()
    if not normalized:
        return ()

    tokens: list[str] = []
    for token in _HEX_COLOR_RE.findall(normalized):
        if token not in tokens:
            tokens.append(token)
    for token in _FUNCTION_COLOR_RE.findall(normalized):
        if token not in tokens:
            tokens.append(token)
    return tuple(tokens)


def _build_report(
    prototype_structure: PrototypeStructure,
    scheme_colors: tuple,
) -> EffectColorReport:
    colors_inventory = build_inventory_from_scheme_colors(scheme_colors)
    entries: list[EffectColorEntry] = []
    entry_index = 0

    for element in prototype_structure:
        for property_model in prototype_structure.properties_for(element):
            if (
                property_model.classification != "effect"
                and property_model.name not in _EFFECT_COLOR_PROPERTIES
            ):
                continue

            effect_colors = _extract_effect_colors(property_model.value)
            if not effect_colors:
                continue

            color_tokens: list[EffectColorToken] = []
            seen_signatures: set[tuple[str, float]] = set()
            for token in effect_colors:
                try:
                    hex_value = color_registry.format_color(token, "hex")
                    alpha = color_registry.alpha_of(token)
                except Exception:
                    continue

                signature = (hex_value, round(alpha, 4))
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)

                color_entry = colors_inventory.entry_by_value(token)
                color_tokens.append(
                    EffectColorToken(
                        value=token,
                        hex_value=hex_value,
                        alpha=alpha,
                        color_id=color_entry.color_id if color_entry is not None else None,
                    )
                )

            if not color_tokens:
                continue

            entry_index += 1
            entries.append(
                EffectColorEntry(
                    effect_id=f"effect-{entry_index}",
                    element_id=element.node_id,
                    tag_name=element.tag_name,
                    selector_hint=element.selector,
                    property_name=property_model.name,
                    resolved_value=property_model.value,
                    style_id=property_model.style_id,
                    declaration_id=property_model.declaration_id,
                    declared_property=property_model.declared_property,
                    colors=tuple(color_tokens),
                )
            )

    return EffectColorReport(entries=tuple(entries))


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("derived.effect_color_report"):
        return context

    context.trace.add_stage_event(CONTRACT.name, "start")
    report = _build_report(
        context.get("prototype_structure"),
        tuple(context.get("scheme.colors")),
    )
    context.set("derived.effect_color_report", report)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "effect_entry_count": len(report),
            "effect_property_count": len(report.to_dict().get("by_property") or ()),
        },
    )
    return context
