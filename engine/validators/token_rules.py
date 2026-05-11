from __future__ import annotations

from collections import defaultdict
import re
from typing import Iterable

from engine.adapters.color_service import color_registry
from engine.domain.data.tokens import TRANSFORMATION_ORDER, TRANSFORMATION_RULES
from engine.domain.models.color import Color
from engine.domain.models.palette import TonalPaletteModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.token import (
    Token,
    TokenInventory,
    TokenState,
    TokenValidationModel,
    TokenValidationStatus,
)
from engine.domain.utils.token import resolve_initial_contrast, select_same_palette_tone

_COLOR_FRAGMENT_RE = re.compile(
    r"(#[0-9a-fA-F]{3,8}\b|(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\([^)]+\)|\b[a-zA-Z][a-zA-Z-]*\b)",
    re.IGNORECASE,
)


def _append_validation(
    token: Token,
    *,
    rule_id: str,
    status: TokenValidationStatus | str,
    reason: str,
    metrics: dict[str, float | str | int] | None = None,
    before: dict[str, float | str | int] | None = None,
    after: dict[str, float | str | int] | None = None,
) -> Token:
    return token.with_validation(
        TokenValidationModel(
            rule_id=rule_id,
            status=status,
            reason=reason,
            metrics=metrics or {},
            before=before or {},
            after=after or {},
        )
    )


def _color_by_value(colors: tuple[Color, ...], value: str) -> Color | None:
    try:
        hex_value = color_registry.format_color(value, "hex")
        alpha = color_registry.alpha_of(value)
    except Exception:
        return None
    return next(
        (
            entry
            for entry in colors
            if entry.hex_value == hex_value and round(entry.alpha, 4) == round(alpha, 4)
        ),
        None,
    )


def _palette_by_id(
    palettes: tuple[TonalPaletteModel, ...],
    palette_id: str,
) -> TonalPaletteModel | None:
    normalized = str(palette_id or "").strip()
    return next((palette for palette in palettes if palette.palette_id == normalized), None)


def _achromatic_palette(palettes: tuple[TonalPaletteModel, ...]) -> TonalPaletteModel | None:
    return next(
        (palette for palette in palettes if palette.palette_type.value == "achromatic"),
        None,
    )


def _foundation_for_tone_targets(
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
    tone_targets: tuple[int, ...],
) -> Token | None:
    palette = _achromatic_palette(palettes)
    if palette is None:
        return None
    for tone in tone_targets:
        foundation = next(
            (
                token
                for token in tokens
                if token.is_foundation
                and palette.palette_id in token.source_palette_ids
                and token.tone == int(tone)
            ),
            None,
        )
        if foundation is not None:
            return foundation
    return None


def _same_palette_foundation_for_tone_targets(
    token: Token,
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
    tone_targets: tuple[int, ...],
) -> Token | None:
    palette_ids = tuple(dict.fromkeys(token.source_palette_ids).keys())
    current_tone = int(token.tone or 50)
    allowed_tones = {int(tone) for tone in tone_targets}
    for palette_id in palette_ids:
        palette = _palette_by_id(palettes, palette_id)
        if palette is None:
            continue
        candidates = sorted(
            (
                tone_stop
                for tone_stop in palette.tones
                if int(tone_stop.tone) in allowed_tones
            ),
            key=lambda tone_stop: (
                abs(int(tone_stop.tone) - current_tone),
                int(tone_stop.tone),
            ),
        )
        for tone_stop in candidates:
            foundation = next(
                (
                    item
                    for item in tokens
                    if item.is_foundation
                    and palette.palette_id in item.source_palette_ids
                    and item.tone == int(tone_stop.tone)
                ),
                None,
            )
            if foundation is not None:
                return foundation
    return None


def _foundation_for_color_entry_tone_targets(
    color_entry: Color,
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
    tone_targets: tuple[int, ...],
) -> Token | None:
    palette_id = color_entry.mapped_palette_id
    current_tone = int(color_entry.mapped_tone or 50)
    allowed_tones = {int(tone) for tone in tone_targets}
    if palette_id:
        palette = _palette_by_id(palettes, palette_id)
        if palette is not None:
            candidates = sorted(
                (
                    tone_stop
                    for tone_stop in palette.tones
                    if int(tone_stop.tone) in allowed_tones
                ),
                key=lambda tone_stop: (
                    abs(int(tone_stop.tone) - current_tone),
                    int(tone_stop.tone),
                ),
            )
            for tone_stop in candidates:
                foundation = next(
                    (
                        item
                        for item in tokens
                        if item.is_foundation
                        and palette.palette_id in item.source_palette_ids
                        and item.tone == int(tone_stop.tone)
                    ),
                    None,
                )
                if foundation is not None:
                    return foundation
    return _foundation_for_tone_targets(palettes, tokens, tone_targets)


def _remap_effect_value(
    token: Token,
    colors: tuple[Color, ...],
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
    tone_targets: tuple[int, ...],
) -> str | None:
    changed = False

    def _replace(match: re.Match[str]) -> str:
        nonlocal changed
        fragment = str(match.group(0) or "").strip()
        if not fragment:
            return match.group(0)
        color_entry = _color_by_value(colors, fragment)
        if color_entry is None:
            return match.group(0)
        foundation = _foundation_for_color_entry_tone_targets(
            color_entry,
            palettes,
            tokens,
            tone_targets,
        )
        if foundation is None:
            return match.group(0)
        replacement = foundation.resolved_value
        if replacement.strip().lower() != fragment.lower():
            changed = True
        return replacement

    updated = _COLOR_FRAGMENT_RE.sub(_replace, token.resolved_value)
    return updated if changed else None


def _primary_background(
    token: Token,
    prototype_structure: PrototypeStructure,
    colors: tuple[Color, ...],
) -> tuple[str | None, str | None]:
    for element_id in token.assigned_element_ids or token.source_element_ids:
        background = prototype_structure.effective_background_of(element_id, colors)
        if background is not None:
            return background.value, background.color_id
    return None, None


def _min_text_contrast(token: Token, prototype_structure: PrototypeStructure) -> float:
    for element_id in token.assigned_element_ids or token.source_element_ids:
        entry = prototype_structure.node_by_id(element_id)
        if entry is not None and entry.tag_name.lower() in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            return float(
                TRANSFORMATION_RULES["text"].get("large_text_minimum_contrast", 3.0)  # type: ignore[index]
            )
    return float(TRANSFORMATION_RULES["text"].get("minimum_contrast", 4.5))  # type: ignore[index]


def _apply_surface_alias(
    token: Token,
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
    *,
    rule_id: str,
    tone_targets: tuple[int, ...],
    reason: str,
) -> Token:
    foundation = _same_palette_foundation_for_tone_targets(token, palettes, tokens, tone_targets)
    if foundation is None:
        foundation = _foundation_for_tone_targets(palettes, tokens, tone_targets)
    if foundation is None:
        return token
    updated = token.with_alias(
        foundation.path_string,
        resolved_value=foundation.resolved_value,
        state=TokenState.VALIDATED,
    ).with_sources(palette_ids=foundation.source_palette_ids)
    return _append_validation(
        updated,
        rule_id=rule_id,
        status=TokenValidationStatus.ADJUSTED,
        reason=reason,
        before={"resolved_value": token.resolved_value},
        after={"resolved_value": foundation.resolved_value, "alias_to": foundation.path_string},
    )


def _stage_applies(token: Token, stage_name: str) -> bool:
    rule = TRANSFORMATION_RULES[stage_name]
    properties = tuple(rule.get("properties") or ())
    elements = tuple(rule.get("elements") or ())
    if token.property_id not in properties:
        return False
    if token.is_foundation:
        return False
    if stage_name == "component_promotion":
        return token.is_semantic
    if token.is_component:
        return False
    return token.element_key in elements


def _apply_main_surface(
    token: Token,
    prototype_structure: PrototypeStructure,
    colors: tuple[Color, ...],
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
) -> Token:
    if token.property_id == "background-color":
        return _apply_surface_alias(
            token,
            palettes,
            tokens,
            rule_id="main_surface",
            tone_targets=tuple(TRANSFORMATION_RULES["main_surface"].get("tone_targets") or (0, 10)),
            reason="Main surface remapped to darker same-palette tones with neutral fallback.",
        )
    if token.property_id == "background-image":
        updated_value = _remap_effect_value(
            token,
            colors,
            palettes,
            tokens,
            tuple(TRANSFORMATION_RULES["main_surface"].get("tone_targets") or (0, 10)),
        )
        if updated_value is None:
            return _append_validation(
                token,
                rule_id="main_surface",
                status=TokenValidationStatus.PASSED,
                reason="Main surface background image preserved because no mapped color stops were found.",
            )
        updated = token.with_resolved_value(
            value=updated_value,
            resolved_value=updated_value,
            state=TokenState.VALIDATED,
        )
        return _append_validation(
            updated,
            rule_id="main_surface",
            status=TokenValidationStatus.ADJUSTED,
            reason="Main surface gradient/image recolored within the original palette family when possible.",
            before={"resolved_value": token.resolved_value},
            after={"resolved_value": updated_value},
        )
    return _append_validation(
        token,
        rule_id="main_surface",
        status=TokenValidationStatus.SKIPPED,
        reason="Main surface rule only rewrites background-color/background-image in V1.",
    )


def _apply_shadow_elevation(
    token: Token,
    prototype_structure: PrototypeStructure,
    colors: tuple[Color, ...],
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
) -> Token:
    if token.element_key in TRANSFORMATION_RULES["shadow_elevation"].get("prefer_none_for", ()):  # type: ignore[index]
        updated = token.with_resolved_value(value="none", resolved_value="none", state=TokenState.VALIDATED)
        return _append_validation(
            updated,
            rule_id="shadow_elevation",
            status=TokenValidationStatus.ADJUSTED,
            reason="Decorative shadows were removed from non-composed surfaces.",
            before={"resolved_value": token.resolved_value},
            after={"resolved_value": "none"},
        )
    updated_value = _remap_effect_value(token, colors, palettes, tokens, (20, 30, 40))
    if updated_value is not None:
        updated = token.with_resolved_value(
            value=updated_value,
            resolved_value=updated_value,
            state=TokenState.VALIDATED,
        )
        return _append_validation(
            updated,
            rule_id="shadow_elevation",
            status=TokenValidationStatus.ADJUSTED,
            reason="Effect colors were remapped to darker same-palette tones for composed elements.",
            before={"resolved_value": token.resolved_value},
            after={"resolved_value": updated_value},
        )
    return _append_validation(
        token,
        rule_id="shadow_elevation",
        status=TokenValidationStatus.PASSED,
        reason="Shadow/elevation token preserved for composed element.",
    )


def _apply_surface(
    token: Token,
    prototype_structure: PrototypeStructure,
    colors: tuple[Color, ...],
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
) -> Token:
    if token.property_id == "background-color":
        return _apply_surface_alias(
            token,
            palettes,
            tokens,
            rule_id="surface",
            tone_targets=tuple(TRANSFORMATION_RULES["surface"].get("tone_targets") or (10, 20)),
            reason="Surface remapped to darker same-palette tones with neutral fallback.",
        )
    if token.property_id == "background-image":
        updated_value = _remap_effect_value(
            token,
            colors,
            palettes,
            tokens,
            tuple(TRANSFORMATION_RULES["surface"].get("tone_targets") or (10, 20)),
        )
        if updated_value is None:
            return _append_validation(
                token,
                rule_id="surface",
                status=TokenValidationStatus.PASSED,
                reason="Surface background image preserved because no mapped color stops were found.",
            )
        updated = token.with_resolved_value(
            value=updated_value,
            resolved_value=updated_value,
            state=TokenState.VALIDATED,
        )
        return _append_validation(
            updated,
            rule_id="surface",
            status=TokenValidationStatus.ADJUSTED,
            reason="Surface gradient/image recolored within the original palette family when possible.",
            before={"resolved_value": token.resolved_value},
            after={"resolved_value": updated_value},
        )
    return _append_validation(
        token,
        rule_id="surface",
        status=TokenValidationStatus.SKIPPED,
        reason="Surface rule only rewrites background-color/background-image in V1.",
    )


def _apply_composed(
    token: Token,
    prototype_structure: PrototypeStructure,
    colors: tuple[Color, ...],
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
) -> Token:
    if token.property_id == "background-color":
        return _apply_surface_alias(
            token,
            palettes,
            tokens,
            rule_id="composed",
            tone_targets=tuple(TRANSFORMATION_RULES["composed"].get("tone_targets") or (20, 30)),
            reason="Composed element remapped to darker same-palette tones with neutral fallback.",
        )
    if token.property_id == "background-image":
        updated_value = _remap_effect_value(
            token,
            colors,
            palettes,
            tokens,
            tuple(TRANSFORMATION_RULES["composed"].get("tone_targets") or (20, 30)),
        )
        if updated_value is None:
            return _append_validation(
                token,
                rule_id="composed",
                status=TokenValidationStatus.PASSED,
                reason="Composed background image preserved because no mapped color stops were found.",
            )
        updated = token.with_resolved_value(
            value=updated_value,
            resolved_value=updated_value,
            state=TokenState.VALIDATED,
        )
        return _append_validation(
            updated,
            rule_id="composed",
            status=TokenValidationStatus.ADJUSTED,
            reason="Composed gradient/image recolored within the original palette family when possible.",
            before={"resolved_value": token.resolved_value},
            after={"resolved_value": updated_value},
        )
    if token.property_id in {"box-shadow", "text-shadow"}:
        return _append_validation(
            token,
            rule_id="composed",
            status=TokenValidationStatus.SKIPPED,
            reason="Composed effect tokens are handled by the shadow_elevation stage.",
        )
    background_value, background_color_id = _primary_background(token, prototype_structure, colors)
    if background_value is None:
        return _append_validation(
            token,
            rule_id="composed",
            status=TokenValidationStatus.SKIPPED,
            reason="No effective background was resolved for the composed token.",
        )
    updated = select_same_palette_tone(
        token,
        palettes,
        tokens,
        background_value=background_value,
        min_contrast=3.0,
    )
    if updated is None:
        return _append_validation(
            token,
            rule_id="composed",
            status=TokenValidationStatus.FAILED,
            reason="No same-palette tone satisfied the minimum contrast for composed element token.",
            before={"background_color_id": background_color_id or ""},
        )
    return _append_validation(
        updated,
        rule_id="composed",
        status=TokenValidationStatus.ADJUSTED,
        reason="Composed token tone adjusted within the same palette.",
        before={"resolved_value": token.resolved_value},
        after={"resolved_value": updated.resolved_value},
    )


def _apply_foreground_non_text(
    token: Token,
    prototype_structure: PrototypeStructure,
    colors: tuple[Color, ...],
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
) -> Token:
    background_value, background_color_id = _primary_background(token, prototype_structure, colors)
    if background_value is None:
        return _append_validation(
            token,
            rule_id="foreground_non_text",
            status=TokenValidationStatus.SKIPPED,
            reason="No effective background was resolved for the non-text foreground token.",
        )
    updated = select_same_palette_tone(
        token,
        palettes,
        tokens,
        background_value=background_value,
        min_contrast=float(TRANSFORMATION_RULES["foreground_non_text"].get("minimum_contrast", 3.0)),  # type: ignore[index]
    )
    if updated is None:
        ratio = resolve_initial_contrast(token.resolved_value, background_value) or 0.0
        return _append_validation(
            token,
            rule_id="foreground_non_text",
            status=TokenValidationStatus.FAILED,
            reason="No tone satisfied the minimum non-text contrast.",
            metrics={"contrast": round(ratio, 4), "minimum": 3.0},
            before={"background_color_id": background_color_id or ""},
        )
    ratio = resolve_initial_contrast(updated.resolved_value, background_value) or 0.0
    return _append_validation(
        updated,
        rule_id="foreground_non_text",
        status=TokenValidationStatus.ADJUSTED,
        reason="Non-text foreground adjusted to satisfy minimum contrast.",
        metrics={"contrast": round(ratio, 4), "minimum": 3.0},
        before={"resolved_value": token.resolved_value},
        after={"resolved_value": updated.resolved_value},
    )


def _apply_text(
    token: Token,
    prototype_structure: PrototypeStructure,
    colors: tuple[Color, ...],
    palettes: tuple[TonalPaletteModel, ...],
    tokens: TokenInventory,
) -> Token:
    background_value, background_color_id = _primary_background(token, prototype_structure, colors)
    if background_value is None:
        return _append_validation(
            token,
            rule_id="text",
            status=TokenValidationStatus.SKIPPED,
            reason="No effective background was resolved for the text token.",
        )
    minimum = _min_text_contrast(token, prototype_structure)
    updated = select_same_palette_tone(
        token,
        palettes,
        tokens,
        background_value=background_value,
        min_contrast=minimum,
    )
    ratio = resolve_initial_contrast(token.resolved_value, background_value) or 0.0
    if updated is None:
        return _append_validation(
            token,
            rule_id="text",
            status=TokenValidationStatus.FAILED,
            reason="No tone satisfied the minimum text contrast.",
            metrics={"contrast": round(ratio, 4), "minimum": minimum},
            before={"background_color_id": background_color_id or ""},
        )
    updated_ratio = resolve_initial_contrast(updated.resolved_value, background_value) or minimum
    status = (
        TokenValidationStatus.PASSED
        if round(updated_ratio, 4) == round(ratio, 4) and updated.resolved_value == token.resolved_value
        else TokenValidationStatus.ADJUSTED
    )
    return _append_validation(
        updated,
        rule_id="text",
        status=status,
        reason="Text token evaluated against the transformed background.",
        metrics={"contrast": round(updated_ratio, 4), "minimum": minimum},
        before={"resolved_value": token.resolved_value},
        after={"resolved_value": updated.resolved_value},
    )


def _promote_component_conflicts(tokens: TokenInventory) -> TokenInventory:
    grouped: dict[str, list[Token]] = defaultdict(list)
    passthrough: list[Token] = []
    for token in tokens:
        if token.is_semantic:
            grouped[token.path_string].append(token)
        else:
            passthrough.append(token)

    promoted: list[Token] = []
    for path_string, items in grouped.items():
        unique_values = {(item.alias_to or "", item.resolved_value) for item in items}
        if len(unique_values) <= 1:
            promoted.extend(items)
            continue
        for index, item in enumerate(items, start=1):
            component_name = f"{item.element_key}_{index}"
            component_path = ("glow", component_name, item.property_id or "property", *(item.value_label or "none").split("."))
            promoted.append(
                Token.component(
                    path=component_path,
                    alias_to=item.alias_to,
                    resolved_value=item.resolved_value,
                    property_id=item.property_id or "property",
                    value_label=item.value_label or "none",
                    source_element_ids=item.source_element_ids,
                    assigned_element_ids=item.assigned_element_ids,
                    source_property_refs=item.source_property_refs,
                    source_color_ids=item.source_color_ids,
                    source_style_ids=item.source_style_ids,
                    source_palette_ids=item.source_palette_ids,
                    source_values=item.source_values,
                    palette_name=item.palette_name,
                    tone=item.tone,
                    created_by_stage=item.created_by_stage,
                    annotations=(*item.annotations, "component_promoted_runtime"),
                )
            )
    return TokenInventory.build([*passthrough, *promoted])


_STAGE_HANDLERS = {
    "main_surface": _apply_main_surface,
    "shadow_elevation": _apply_shadow_elevation,
    "surface": _apply_surface,
    "composed": _apply_composed,
    "foreground_non_text": _apply_foreground_non_text,
    "text": _apply_text,
}


def apply_token_rules(
    tokens: TokenInventory,
    prototype_structure: PrototypeStructure,
    colors: Iterable[Color],
    palettes: tuple[TonalPaletteModel, ...],
) -> TokenInventory:
    current_tokens = tokens
    color_entries = tuple(colors)
    palette_entries = tuple(palettes)

    for stage_name in TRANSFORMATION_ORDER:
        if stage_name == "component_promotion":
            current_tokens = _promote_component_conflicts(current_tokens)
            continue

        handler = _STAGE_HANDLERS[stage_name]
        updated_entries: list[Token] = []
        for token in current_tokens:
            if _stage_applies(token, stage_name):
                updated_entries.append(
                    handler(
                        token,
                        prototype_structure,
                        color_entries,
                        palette_entries,
                        current_tokens,
                    )
                )
            else:
                updated_entries.append(token)
        current_tokens = TokenInventory.build(updated_entries)

    return TokenInventory.build(
        token.with_resolved_value(
            value=token.value,
            resolved_value=token.resolved_value,
            state=TokenState.VALIDATED if token.state == TokenState.DRAFT else token.state,
        )
        for token in current_tokens
    )
