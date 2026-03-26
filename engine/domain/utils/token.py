from __future__ import annotations

import re
from typing import Iterable

from engine.domain.data.tokens import (
    ACTION_PROMOTION_TAGS,
    HTML_TOKEN_OVERRIDES,
    ICON_TAGS,
    PROPERTY_TOKEN_RULES,
    TOKEN_NAMESPACE,
    TOKENIZABLE_PROPERTY_IDS,
    TRANSFORMATION_ORDER,
    VALUE_RULES,
)
from engine.domain.models.color import ColorInventoryEntry
from engine.domain.models.element import ElementColorPropertyModel, ElementInventoryEntry
from engine.domain.models.inventory_graph import InventoryGraphModel
from engine.domain.models.palette import ColorSchemeArtifactModel, TonalPaletteModel
from engine.domain.models.token import Token, TokenInventory
from engine.domain.models.style import ComputedStyleValueModel
from engine.domain.utils.coloraide import alpha_value, color_to_hex, color_to_rgb_tuple, contrast_ratio, rgb_to_css

_SEGMENT_RE = re.compile(r"[^a-z0-9]+")
_ACTION_HINTS = ("btn", "button", "cta", "action", "chip", "pill", "tab")


def _segment(value: str | None, *, default: str = "item") -> str:
    normalized = _SEGMENT_RE.sub("_", str(value or "").strip().lower()).strip("_")
    return normalized or default


def _value_segments(value_label: str) -> tuple[str, ...]:
    return tuple(segment for segment in str(value_label or "").split(".") if segment) or ("none",)


def _style_ref_for(entry: ElementInventoryEntry, color_property: ElementColorPropertyModel) -> str:
    style_id = color_property.winning_style_ref.style_id
    property_name = color_property.property_name
    if style_id:
        return f"{style_id}:{property_name}"
    return f"{entry.node_id}:{property_name}"


def _computed_style_ref_for(
    entry: ElementInventoryEntry,
    property_name: str,
    computed_style: ComputedStyleValueModel,
) -> str:
    style_id = computed_style.style_id
    declared_property = str(computed_style.declared_property or property_name or "").strip().lower()
    property_value = declared_property or str(property_name or "").strip().lower()
    if style_id:
        return f"{style_id}:{property_value}"
    return f"{entry.node_id}:{property_value}"


def _color_value_variants(value: str) -> tuple[str, ...]:
    normalized = str(value or "").strip()
    if not normalized:
        return ()
    variants = {normalized.lower()}
    try:
        variants.add(color_to_hex(normalized).lower())
        variants.add(rgb_to_css(color_to_rgb_tuple(normalized)).lower())
    except Exception:
        pass
    return tuple(sorted(variants))


def _token_path_to_id(path: Iterable[str]) -> str:
    return ".".join(str(item) for item in path if str(item))


def _palette_segment(palette: TonalPaletteModel) -> str:
    return _segment(
        palette.display_name or palette.seed_display_name or palette.seed_name or palette.palette_id,
        default="palette",
    )


def _foundation_path(palette: TonalPaletteModel, tone: int) -> tuple[str, ...]:
    return (TOKEN_NAMESPACE, "color", _palette_segment(palette), str(int(tone)))


def _foundation_token_for(
    tokens: Iterable[Token],
    palette_id: str,
    tone: int,
) -> Token | None:
    return next(
        (
            token
            for token in tokens
            if token.is_foundation
            and palette_id in token.source_palette_ids
            and token.tone == tone
        ),
        None,
    )


def _largest_heading_or_display(entry: ElementInventoryEntry) -> bool:
    return entry.identity.tag.lower() in {"h1", "h2", "h3", "h4", "h5", "h6"}


def _is_action_like_link(entry: ElementInventoryEntry) -> bool:
    if entry.identity.tag.lower() not in ACTION_PROMOTION_TAGS:
        return False
    if (entry.identity.role or "").lower() == "button":
        return True
    candidates = (
        entry.identity.id,
        entry.identity.name,
        *(entry.identity.class_list or ()),
    )
    if any(_segment(candidate) for candidate in candidates if any(hint in str(candidate).lower() for hint in _ACTION_HINTS)):
        return True
    decorative_properties = {
        "background",
        "background-color",
        "border-color",
        "border-top-color",
        "border-right-color",
        "border-bottom-color",
        "border-left-color",
        "border-block-start-color",
        "border-block-end-color",
        "border-inline-start-color",
        "outline-color",
        "box-shadow",
    }
    return any(color_property.property_name in decorative_properties for color_property in entry.color_properties)


def resolve_html_token_element(entry: ElementInventoryEntry, graph: InventoryGraphModel) -> str:
    tag = (entry.identity.tag or "").lower()
    if tag in ICON_TAGS:
        return "icon"
    if tag in ACTION_PROMOTION_TAGS and _is_action_like_link(entry):
        return "composed"
    if tag in HTML_TOKEN_OVERRIDES:
        return HTML_TOKEN_OVERRIDES[tag]
    if entry.flags.is_text_node or bool(str(entry.text or "").strip()):
        return "text"
    return "surface"


def resolve_property_rule(property_id: str) -> dict[str, object] | None:
    return PROPERTY_TOKEN_RULES.get(str(property_id or "").strip().lower())


def resolve_effective_background(
    entry: ElementInventoryEntry,
    graph: InventoryGraphModel,
) -> ColorInventoryEntry | None:
    return graph.effective_background_of(entry.node_id)


def resolve_effective_foreground(
    entry: ElementInventoryEntry,
    property_id: str,
    graph: InventoryGraphModel,
) -> ColorInventoryEntry | None:
    if property_id == "color":
        return graph.effective_color_of(entry.node_id)
    return graph.color_by_id(next((item.color_id for item in entry.color_properties if item.property_name == property_id and item.color_id), ""))  # type: ignore[arg-type]


def resolve_initial_contrast(value: str, background: str) -> float | None:
    try:
        return float(contrast_ratio(value, background))
    except Exception:
        return None


def resolve_value_label(
    property_id: str,
    contrast: float | None,
    color: str | None,
    background: str | None,
    effect: str | None,
) -> str:
    normalized_property = str(property_id or "").strip().lower()
    normalized_effect = str(effect or "").strip().lower()

    if normalized_property == "background-image":
        if not normalized_effect or normalized_effect == "none":
            return "none"
        if "gradient" in normalized_effect:
            return "gradient"
        if "url(" in normalized_effect:
            return "image"
        return "overlay"

    if normalized_property in {"box-shadow", "text-shadow"}:
        if not normalized_effect or normalized_effect == "none":
            return "none"
        try:
            if alpha_value(effect or normalized_effect) <= float(VALUE_RULES["overlay_alpha_threshold"]):
                return "overlay"
        except Exception:
            pass
        if "inset" in normalized_effect:
            return "overlay"
        return "elevated"

    try:
        if alpha_value(color or effect or "") <= float(VALUE_RULES["transparent_alpha_threshold"]):
            return "transparent"
    except Exception:
        pass

    if contrast is None:
        return "subtle.1"

    emphasis_rules = VALUE_RULES["contrast_ladder"]["emphasis"]  # type: ignore[index]
    subtle_rules = VALUE_RULES["contrast_ladder"]["subtle"]  # type: ignore[index]
    for label, minimum in emphasis_rules:
        if contrast >= float(minimum):
            return str(label)
    for label, minimum in subtle_rules:
        if contrast >= float(minimum):
            return str(label)
    return "subtle.1"


def select_same_palette_tone(
    token: Token,
    graph: InventoryGraphModel,
    tokens: Iterable[Token],
    *,
    background_value: str,
    min_contrast: float,
    preferred_tones: Iterable[int] | None = None,
) -> Token | None:
    candidates: list[tuple[int, float, Token]] = []
    current_tone = int(token.tone or 50)
    tone_order = tuple(int(item) for item in (preferred_tones or ()))

    palette_ids = token.source_palette_ids
    if not palette_ids:
        neutral_palette = next(
            (palette for palette in graph.palettes if palette.palette_type.value == "achromatic"),
            None,
        )
        palette_ids = (neutral_palette.palette_id,) if neutral_palette is not None else ()

    for palette_id in palette_ids:
        palette = graph.palette_by_id(palette_id)
        if palette is None:
            continue
        tone_candidates = list(palette.tones)
        if tone_order:
            ordered_by_preference: list = []
            seen: set[int] = set()
            for preferred in tone_order:
                for tone_stop in palette.tones:
                    if int(tone_stop.tone) == int(preferred) and int(tone_stop.tone) not in seen:
                        ordered_by_preference.append(tone_stop)
                        seen.add(int(tone_stop.tone))
            ordered_by_preference.extend(
                tone_stop for tone_stop in palette.tones if int(tone_stop.tone) not in seen
            )
            tone_candidates = ordered_by_preference

        for tone_stop in tone_candidates:
            ratio = resolve_initial_contrast(tone_stop.hex_value, background_value)
            if ratio is None or ratio < min_contrast:
                continue
            foundation = _foundation_token_for(tokens, palette.palette_id, int(tone_stop.tone))
            if foundation is None:
                continue
            candidates.append((abs(int(tone_stop.tone) - current_tone), -ratio, foundation))

    if not candidates:
        return None

    foundation = sorted(candidates, key=lambda item: (item[0], item[1], item[2].path_string))[0][2]
    return token.with_alias(foundation.path_string, resolved_value=foundation.resolved_value, state="validated").with_sources(
        palette_ids=foundation.source_palette_ids,
    )


def _fallback_foundation_token(color: ColorInventoryEntry) -> Token:
    return Token.foundation(
        path=(TOKEN_NAMESPACE, "color", "custom", _segment(color.color_id, default="color")),
        resolved_value=color.hex_value,
        source_color_ids=(color.color_id,),
        created_by_stage="set_tokens",
        annotations=("fallback_foundation_token",),
    )


def resolve_foundation_color(
    color_entry: ColorInventoryEntry,
    color_scheme: ColorSchemeArtifactModel,
    base_token_map: dict[tuple[str, int], Token],
    fallback_tokens: dict[str, Token],
) -> Token:
    if color_entry.mapped_palette_id is not None and color_entry.mapped_tone is not None:
        foundation = base_token_map.get((color_entry.mapped_palette_id, int(color_entry.mapped_tone)))
        if foundation is not None:
            return foundation
    return fallback_tokens.setdefault(color_entry.color_id, _fallback_foundation_token(color_entry))


def _build_base_tokens(
    color_scheme: ColorSchemeArtifactModel,
) -> tuple[tuple[Token, ...], dict[tuple[str, int], Token]]:
    tokens: list[Token] = []
    by_palette_tone: dict[tuple[str, int], Token] = {}
    for palette in color_scheme.core_palettes:
        for tone_stop in palette.tones:
            token = Token.foundation(
                path=_foundation_path(palette, tone_stop.tone),
                resolved_value=tone_stop.hex_value,
                palette_name=palette.display_name or palette.seed_display_name or palette.seed_name,
                tone=int(tone_stop.tone),
                source_palette_ids=(palette.palette_id,),
                created_by_stage="set_tokens",
                annotations=("foundation_color_token",),
            )
            tokens.append(token)
            by_palette_tone[(palette.palette_id, int(tone_stop.tone))] = token
    return tuple(tokens), by_palette_tone


def _component_name(entry: ElementInventoryEntry, element_key: str) -> str:
    candidates = (
        entry.identity.id,
        *(entry.identity.class_list or ()),
        entry.identity.name,
        entry.identity.role,
        entry.identity.tag,
    )
    for candidate in candidates:
        normalized = _segment(candidate)
        if normalized:
            return normalized
    return f"{element_key}_{entry.document_order}"


def _merge_tokens(tokens: Iterable[Token]) -> Token:
    ordered = tuple(tokens)
    first = ordered[0]
    return first.with_sources(
        element_ids=(item for token in ordered for item in token.source_element_ids),
        color_ids=(item for token in ordered for item in token.source_color_ids),
        style_ids=(item for token in ordered for item in token.source_style_ids),
        palette_ids=(item for token in ordered for item in token.source_palette_ids),
        values=(item for token in ordered for item in token.source_values),
        property_refs=(item for token in ordered for item in token.source_property_refs),
    ).with_assignment(
        element_ids=(item for token in ordered for item in token.assigned_element_ids),
        property_refs=(item for token in ordered for item in token.source_property_refs),
    )


def promote_to_component_if_conflict(
    tokens: Iterable[tuple[Token, ElementInventoryEntry]],
) -> tuple[Token, ...]:
    ordered = tuple(tokens)
    if not ordered:
        return ()
    first_token = ordered[0][0]
    unique_values = {
        (token.alias_to or "", token.resolved_value)
        for token, _ in ordered
    }
    if len(unique_values) <= 1:
        return (_merge_tokens(token for token, _ in ordered),)

    grouped: dict[str, list[Token]] = {}
    for token, entry in ordered:
        component = _component_name(entry, token.element_key or "component")
        component_path = (TOKEN_NAMESPACE, component, token.property_id or "property", *_value_segments(token.value_label or "none"))
        promoted = Token.component(
            path=component_path,
            alias_to=token.alias_to,
            resolved_value=token.resolved_value,
            property_id=token.property_id or "property",
            value_label=token.value_label or "none",
            source_element_ids=token.source_element_ids,
            assigned_element_ids=token.assigned_element_ids,
            source_property_refs=token.source_property_refs,
            source_color_ids=token.source_color_ids,
            source_style_ids=token.source_style_ids,
            source_palette_ids=token.source_palette_ids,
            source_values=token.source_values,
            palette_name=token.palette_name,
            tone=token.tone,
            created_by_stage=token.created_by_stage,
            annotations=(*token.annotations, "component_promoted"),
        )
        grouped.setdefault(promoted.path_string, []).append(promoted)
    return tuple(_merge_tokens(items) for items in grouped.values())


def _semantic_candidate(
    entry: ElementInventoryEntry,
    color_property: ElementColorPropertyModel,
    color_entry: ColorInventoryEntry | None,
    graph: InventoryGraphModel,
    color_scheme: ColorSchemeArtifactModel,
    base_token_map: dict[tuple[str, int], Token],
    fallback_tokens: dict[str, Token],
    ) -> Token | None:
    property_name = str(color_property.property_name or "").strip().lower()
    if property_name not in TOKENIZABLE_PROPERTY_IDS:
        return None
    property_rule = resolve_property_rule(property_name)
    if property_rule is None:
        return None

    element_key = resolve_html_token_element(entry, graph)
    allowed_elements = tuple(property_rule.get("elements") or ())
    if allowed_elements and element_key not in allowed_elements:
        if property_name in {"fill", "stroke"}:
            element_key = "icon"
        elif property_name == "color":
            element_key = "text" if resolve_html_token_element(entry, graph) != "composed" else "composed"
        elif property_name.startswith(("border", "outline")):
            element_key = "composed" if element_key == "text" else element_key

    background = resolve_effective_background(entry, graph)
    background_value = background.value if background is not None else None
    contrast = None
    source_color_value = color_entry.value if color_entry is not None else color_property.resolved_value
    if bool(property_rule.get("uses_contrast")) and background_value:
        contrast = resolve_initial_contrast(source_color_value, background_value)

    value_label = resolve_value_label(
        property_name,
        contrast,
        source_color_value,
        background_value,
        color_property.resolved_value,
    )
    foundation = (
        resolve_foundation_color(color_entry, color_scheme, base_token_map, fallback_tokens)
        if color_entry is not None
        else None
    )
    alias_to = (
        foundation.path_string
        if foundation is not None and property_name not in {"background-image", "box-shadow", "text-shadow"}
        else None
    )
    return Token.semantic(
        path=(TOKEN_NAMESPACE, element_key, property_name, *_value_segments(value_label)),
        alias_to=alias_to,
        resolved_value=(
            foundation.resolved_value
            if alias_to and foundation is not None
            else (color_property.resolved_value or (color_entry.value if color_entry is not None else ""))
        ),
        element_key=element_key,
        property_id=property_name,
        value_label=value_label,
        source_element_ids=(entry.node_id,),
        assigned_element_ids=(entry.node_id,),
        source_property_refs=(_style_ref_for(entry, color_property),),
        source_color_ids=((color_entry.color_id,) if color_entry is not None else ()),
        source_style_ids=((color_property.winning_style_ref.style_id,) if color_property.winning_style_ref.style_id else ()),
        source_palette_ids=tuple(foundation.source_palette_ids if foundation is not None else ()),
        source_values=(
            color_property.resolved_value,
            *(_color_value_variants(color_entry.value if color_entry is not None else "")),
            *(_color_value_variants(color_entry.hex_value if color_entry is not None else "")),
            *(_color_value_variants(rgb_to_css(color_entry.rgb) if color_entry is not None else "")),
        ),
        palette_name=(foundation.palette_name if foundation is not None else None),
        tone=(foundation.tone if foundation is not None else None),
        created_by_stage="set_tokens",
        annotations=("semantic_token", property_rule.get("bucket", "unknown")),
    )


def _tokenizable_computed_fallbacks(
    entry: ElementInventoryEntry,
) -> tuple[tuple[str, ComputedStyleValueModel], ...]:
    effect_properties = {"background-image", "box-shadow", "text-shadow"}
    color_property_names = {
        str(item.property_name or "").strip().lower()
        for item in entry.iter_color_properties()
        if str(item.property_name or "").strip()
    }
    candidates: list[tuple[str, ComputedStyleValueModel]] = []
    for property_name, computed_style in entry.iter_computed_styles():
        normalized_property = str(property_name or "").strip().lower()
        if normalized_property in color_property_names and normalized_property not in effect_properties:
            continue
        if normalized_property not in TOKENIZABLE_PROPERTY_IDS:
            continue
        if normalized_property == "background":
            continue
        property_rule = resolve_property_rule(normalized_property)
        if property_rule is None:
            continue
        if not str(computed_style.computed_value or "").strip():
            continue
        candidates.append((normalized_property, computed_style))
    return tuple(candidates)


def _effect_candidate(
    entry: ElementInventoryEntry,
    property_name: str,
    computed_style: ComputedStyleValueModel,
    graph: InventoryGraphModel,
) -> Token | None:
    property_rule = resolve_property_rule(property_name)
    if property_rule is None:
        return None

    element_key = resolve_html_token_element(entry, graph)
    allowed_elements = tuple(property_rule.get("elements") or ())
    if allowed_elements and element_key not in allowed_elements:
        return None

    resolved_value = str(computed_style.computed_value or "").strip()
    if not resolved_value:
        return None

    value_label = resolve_value_label(
        property_name,
        None,
        None,
        None,
        resolved_value,
    )
    declared_property = str(computed_style.declared_property or property_name or "").strip().lower()
    property_refs = {
        _computed_style_ref_for(entry, property_name, computed_style),
        f"{entry.node_id}:{property_name}",
    }
    if declared_property:
        property_refs.add(f"{entry.node_id}:{declared_property}")

    return Token.semantic(
        path=(TOKEN_NAMESPACE, element_key, property_name, *_value_segments(value_label)),
        alias_to=None,
        resolved_value=resolved_value,
        element_key=element_key,
        property_id=property_name,
        value_label=value_label,
        source_element_ids=(entry.node_id,),
        assigned_element_ids=(entry.node_id,),
        source_property_refs=tuple(sorted(property_refs)),
        source_style_ids=((computed_style.style_id,) if computed_style.style_id else ()),
        source_values=(resolved_value,),
        created_by_stage="set_tokens",
        annotations=("semantic_token", property_rule.get("bucket", "unknown"), "effect_property"),
    )


def build_token_inventory(
    graph: InventoryGraphModel,
    color_scheme: ColorSchemeArtifactModel,
) -> TokenInventory:
    base_tokens, base_token_map = _build_base_tokens(color_scheme)
    fallback_tokens: dict[str, Token] = {}
    semantic_candidates: list[tuple[Token, ElementInventoryEntry]] = []

    for entry in graph.elements.visible_entries():
        for color_property in entry.iter_color_properties():
            property_name = str(color_property.property_name or "").strip().lower()
            if property_name not in TOKENIZABLE_PROPERTY_IDS:
                continue
            if property_name in {"background-image", "box-shadow", "text-shadow"}:
                continue
            color_entry = (
                graph.color_by_id(color_property.color_id)
                if color_property.color_id
                else None
            )
            token = _semantic_candidate(
                entry,
                color_property,
                color_entry,
                graph,
                color_scheme,
                base_token_map,
                fallback_tokens,
            )
            if token is not None:
                semantic_candidates.append((token, entry))

        for index, (property_name, computed_style) in enumerate(
            _tokenizable_computed_fallbacks(entry),
            start=1,
        ):
            if property_name in {"background-image", "box-shadow", "text-shadow"}:
                token = _effect_candidate(entry, property_name, computed_style, graph)
            else:
                color_entry = graph.colors.entry_by_value(computed_style.computed_value)
                computed_color_property = ElementColorPropertyModel.from_computed_style(
                    node_id=entry.node_id,
                    index=index,
                    property_name=property_name,
                    computed_style=computed_style,
                    color_id=(color_entry.color_id if color_entry is not None else None),
                )
                token = _semantic_candidate(
                    entry,
                    computed_color_property,
                    color_entry,
                    graph,
                    color_scheme,
                    base_token_map,
                    fallback_tokens,
                )
            if token is not None:
                semantic_candidates.append((token, entry))

    grouped: dict[str, list[tuple[Token, ElementInventoryEntry]]] = {}
    for token, entry in semantic_candidates:
        grouped.setdefault(token.path_string, []).append((token, entry))

    semantic_tokens: list[Token] = []
    for grouped_tokens in grouped.values():
        semantic_tokens.extend(promote_to_component_if_conflict(grouped_tokens))

    return TokenInventory.build([*base_tokens, *fallback_tokens.values(), *semantic_tokens])
