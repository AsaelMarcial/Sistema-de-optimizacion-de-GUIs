from __future__ import annotations

from collections import defaultdict

from engine.domain.data.tokens import TRANSFORMATION_ORDER, TRANSFORMATION_RULES
from engine.domain.models.inventory_graph import InventoryGraphModel
from engine.domain.models.token import (
    Token,
    TokenInventory,
    TokenState,
    TokenValidationModel,
    TokenValidationStatus,
)
from engine.domain.utils.token import resolve_initial_contrast, select_same_palette_tone


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


def _achromatic_palette(graph: InventoryGraphModel):
    return next(
        (palette for palette in graph.palettes if palette.palette_type.value == "achromatic"),
        None,
    )


def _foundation_for_tone_targets(
    graph: InventoryGraphModel,
    tone_targets: tuple[int, ...],
) -> Token | None:
    palette = _achromatic_palette(graph)
    if palette is None:
        return None
    for tone in tone_targets:
        foundation = next(
            (
                token
                for token in graph.tokens
                if token.is_foundation
                and palette.palette_id in token.source_palette_ids
                and token.tone == int(tone)
            ),
            None,
        )
        if foundation is not None:
            return foundation
    return None


def _primary_background(token: Token, graph: InventoryGraphModel) -> tuple[str | None, str | None]:
    for element_id in token.assigned_element_ids or token.source_element_ids:
        background = graph.effective_background_of(element_id)
        if background is not None:
            return background.value, background.color_id
    return None, None


def _min_text_contrast(token: Token, graph: InventoryGraphModel) -> float:
    for element_id in token.assigned_element_ids or token.source_element_ids:
        entry = graph.element_by_id(element_id)
        if entry is not None and entry.identity.tag.lower() in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            return float(
                TRANSFORMATION_RULES["text"].get("large_text_minimum_contrast", 3.0)  # type: ignore[index]
            )
    return float(TRANSFORMATION_RULES["text"].get("minimum_contrast", 4.5))  # type: ignore[index]


def _apply_surface_alias(
    token: Token,
    graph: InventoryGraphModel,
    *,
    rule_id: str,
    tone_targets: tuple[int, ...],
    reason: str,
) -> Token:
    foundation = _foundation_for_tone_targets(graph, tone_targets)
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


def _apply_main_surface(token: Token, graph: InventoryGraphModel) -> Token:
    if token.property_id == "background-color":
        return _apply_surface_alias(
            token,
            graph,
            rule_id="main_surface",
            tone_targets=tuple(TRANSFORMATION_RULES["main_surface"].get("tone_targets") or (0, 10)),
            reason="Main surface remapped to achromatic foundation tones.",
        )
    return _append_validation(
        token,
        rule_id="main_surface",
        status=TokenValidationStatus.SKIPPED,
        reason="Main surface rule only rewrites background-color in V1.",
    )


def _apply_shadow_elevation(token: Token, graph: InventoryGraphModel) -> Token:
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
    return _append_validation(
        token,
        rule_id="shadow_elevation",
        status=TokenValidationStatus.PASSED,
        reason="Shadow/elevation token preserved for composed element.",
    )


def _apply_surface(token: Token, graph: InventoryGraphModel) -> Token:
    if token.property_id == "background-color":
        return _apply_surface_alias(
            token,
            graph,
            rule_id="surface",
            tone_targets=tuple(TRANSFORMATION_RULES["surface"].get("tone_targets") or (10, 20)),
            reason="Surface remapped to layered achromatic foundation tones.",
        )
    return _append_validation(
        token,
        rule_id="surface",
        status=TokenValidationStatus.SKIPPED,
        reason="Surface rule only rewrites background-color in V1.",
    )


def _apply_composed(token: Token, graph: InventoryGraphModel) -> Token:
    if token.property_id == "background-color":
        return _apply_surface_alias(
            token,
            graph,
            rule_id="composed",
            tone_targets=tuple(TRANSFORMATION_RULES["composed"].get("tone_targets") or (20, 30)),
            reason="Composed element remapped to elevated achromatic foundation tones.",
        )
    background_value, background_color_id = _primary_background(token, graph)
    if background_value is None:
        return _append_validation(
            token,
            rule_id="composed",
            status=TokenValidationStatus.SKIPPED,
            reason="No effective background was resolved for the composed token.",
        )
    updated = select_same_palette_tone(token, graph, background_value=background_value, min_contrast=3.0)
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


def _apply_foreground_non_text(token: Token, graph: InventoryGraphModel) -> Token:
    background_value, background_color_id = _primary_background(token, graph)
    if background_value is None:
        return _append_validation(
            token,
            rule_id="foreground_non_text",
            status=TokenValidationStatus.SKIPPED,
            reason="No effective background was resolved for the non-text foreground token.",
        )
    updated = select_same_palette_tone(
        token,
        graph,
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


def _apply_text(token: Token, graph: InventoryGraphModel) -> Token:
    background_value, background_color_id = _primary_background(token, graph)
    if background_value is None:
        return _append_validation(
            token,
            rule_id="text",
            status=TokenValidationStatus.SKIPPED,
            reason="No effective background was resolved for the text token.",
        )
    minimum = _min_text_contrast(token, graph)
    updated = select_same_palette_tone(token, graph, background_value=background_value, min_contrast=minimum)
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


def apply_token_rules(tokens: TokenInventory, graph: InventoryGraphModel) -> TokenInventory:
    current_tokens = tokens
    current_graph = graph

    for stage_name in TRANSFORMATION_ORDER:
        if stage_name == "component_promotion":
            current_tokens = _promote_component_conflicts(current_tokens)
            current_graph = InventoryGraphModel.build(
                elements=current_graph.elements,
                styles=current_graph.styles,
                colors=current_graph.colors,
                palettes=current_graph.palettes,
                tokens=current_tokens,
            )
            continue

        handler = _STAGE_HANDLERS[stage_name]
        updated_entries: list[Token] = []
        for token in current_tokens:
            if _stage_applies(token, stage_name):
                updated_entries.append(handler(token, current_graph))
            else:
                updated_entries.append(token)
        current_tokens = TokenInventory.build(updated_entries)
        current_graph = InventoryGraphModel.build(
            elements=current_graph.elements,
            styles=current_graph.styles,
            colors=current_graph.colors,
            palettes=current_graph.palettes,
            tokens=current_tokens,
        )

    return TokenInventory.build(
        token.with_resolved_value(
            value=token.value,
            resolved_value=token.resolved_value,
            state=TokenState.VALIDATED if token.state == TokenState.DRAFT else token.state,
        )
        for token in current_tokens
    )
