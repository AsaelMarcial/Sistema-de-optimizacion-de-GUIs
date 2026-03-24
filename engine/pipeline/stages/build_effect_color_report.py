from __future__ import annotations

import re

from engine.adapters.utils.io import save_json
from engine.domain.models.color import ColorInventoryModel
from engine.domain.models.effect_color import (
    EffectColorEntryModel,
    EffectColorReportModel,
    EffectColorTokenModel,
)
from engine.domain.models.element import ElementInventoryModel
from engine.domain.utils.coloraide import alpha_value, color_to_hex
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
        context_value("elements.inventory", ElementInventoryModel),
        context_value("color.inventory", ColorInventoryModel),
        context_value(
            "session.output.paths.original.effect_color_report_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
    ),
    produces=(context_value("inventory.effect_color_report", EffectColorReportModel),),
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
    elements_inventory: ElementInventoryModel,
    colors_inventory: ColorInventoryModel,
) -> EffectColorReportModel:
    entries: list[EffectColorEntryModel] = []
    entry_index = 0

    for element in elements_inventory:
        for property_name, computed_style in sorted(
            element.iter_computed_styles(),
            key=lambda item: item[0],
        ):
            if property_name not in _EFFECT_COLOR_PROPERTIES:
                continue

            effect_colors = _extract_effect_colors(computed_style.computed_value)
            if not effect_colors:
                continue

            color_tokens: list[EffectColorTokenModel] = []
            seen_signatures: set[tuple[str, float]] = set()
            for token in effect_colors:
                try:
                    hex_value = color_to_hex(token)
                    alpha = alpha_value(token)
                except Exception:
                    continue

                signature = (hex_value, round(alpha, 4))
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)

                color_entry = colors_inventory.entry_by_value(token)
                color_tokens.append(
                    EffectColorTokenModel(
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
                EffectColorEntryModel(
                    effect_id=f"effect-{entry_index}",
                    element_id=element.node_id,
                    tag_name=element.identity.tag,
                    selector_hint=element.identity.selector_hint,
                    property_name=property_name,
                    resolved_value=computed_style.computed_value,
                    style_id=computed_style.style_id,
                    declaration_id=computed_style.declaration_id,
                    declared_property=computed_style.declared_property,
                    colors=tuple(color_tokens),
                )
            )

    return EffectColorReportModel(entries=tuple(entries))


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("inventory.effect_color_report"):
        return context

    context.trace.add_stage_event(CONTRACT.name, "start")
    report = _build_report(
        context.get("elements.inventory"),
        context.get("color.inventory"),
    )
    context.set("inventory.effect_color_report", report)
    save_json(
        context.get("session.output.paths.original.effect_color_report_json"),
        report.to_dict(),
        indent=4,
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "effect_entry_count": len(report),
            "effect_property_count": len(report.to_dict().get("by_property") or ()),
        },
    )
    return context
