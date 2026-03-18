from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class CssPropertyCategory(StrEnum):
    APPEARANCE = "appearance"
    BACKGROUND = "background"
    BORDER = "border"
    COLOR = "color"
    DECORATION = "decoration"
    DISPLAY = "display"
    EFFECT = "effect"
    POSITION = "position"
    TYPOGRAPHY = "typography"


class CssColorRole(StrEnum):
    FOREGROUND = "foreground"
    BACKGROUND = "background"
    OTHER = "other"


class CssPropertyId(StrEnum):
    ACCENT_COLOR = "accent-color"
    APPEARANCE = "appearance"
    BACKGROUND = "background"
    BACKGROUND_ATTACHMENT = "background-attachment"
    BACKGROUND_CLIP = "background-clip"
    BACKGROUND_COLOR = "background-color"
    BACKGROUND_IMAGE = "background-image"
    BACKGROUND_ORIGIN = "background-origin"
    BACKGROUND_POSITION = "background-position"
    BACKGROUND_REPEAT = "background-repeat"
    BACKGROUND_SIZE = "background-size"
    BORDER = "border"
    BORDER_BLOCK_END = "border-block-end"
    BORDER_BLOCK_END_COLOR = "border-block-end-color"
    BORDER_BLOCK_START = "border-block-start"
    BORDER_BLOCK_START_COLOR = "border-block-start-color"
    BORDER_BOTTOM = "border-bottom"
    BORDER_BOTTOM_COLOR = "border-bottom-color"
    BORDER_COLOR = "border-color"
    BORDER_INLINE_END = "border-inline-end"
    BORDER_INLINE_START = "border-inline-start"
    BORDER_INLINE_START_COLOR = "border-inline-start-color"
    BORDER_LEFT = "border-left"
    BORDER_LEFT_COLOR = "border-left-color"
    BORDER_RADIUS = "border-radius"
    BORDER_RIGHT = "border-right"
    BORDER_RIGHT_COLOR = "border-right-color"
    BORDER_STYLE = "border-style"
    BORDER_TOP = "border-top"
    BORDER_TOP_COLOR = "border-top-color"
    BORDER_WIDTH = "border-width"
    BOX_SHADOW = "box-shadow"
    CARET = "caret"
    CARET_COLOR = "caret-color"
    COLOR = "color"
    COLUMN_RULE = "column-rule"
    COLUMN_RULE_COLOR = "column-rule-color"
    DISPLAY = "display"
    FILL = "fill"
    FILL_OPACITY = "fill-opacity"
    FILL_RULE = "fill-rule"
    FILTER = "filter"
    FLOOD_COLOR = "flood-color"
    HEIGHT = "height"
    LIGHTING_COLOR = "lighting-color"
    OBJECT_FIT = "object-fit"
    OBJECT_POSITION = "object-position"
    OPACITY = "opacity"
    OUTLINE = "outline"
    OUTLINE_COLOR = "outline-color"
    OUTLINE_OFFSET = "outline-offset"
    OUTLINE_STYLE = "outline-style"
    OUTLINE_WIDTH = "outline-width"
    POSITION = "position"
    STOP_COLOR = "stop-color"
    STROKE = "stroke"
    STROKE_OPACITY = "stroke-opacity"
    TEXT_DECORATION = "text-decoration"
    TEXT_DECORATION_COLOR = "text-decoration-color"
    TEXT_DECORATION_LINE = "text-decoration-line"
    TEXT_DECORATION_STYLE = "text-decoration-style"
    TEXT_DECORATION_THICKNESS = "text-decoration-thickness"
    TEXT_EMPHASIS = "text-emphasis"
    TEXT_EMPHASIS_COLOR = "text-emphasis-color"
    TEXT_SHADOW = "text-shadow"
    VISIBILITY = "visibility"
    WIDTH = "width"
    Z_INDEX = "z-index"


@dataclass(frozen=True, slots=True)
class CssPropertySpec:
    property_id: CssPropertyId
    categories: tuple[CssPropertyCategory, ...]
    color_role: CssColorRole | None = None
    computed_aliases: tuple[str, ...] = ()
    shorthand_for: tuple[CssPropertyId, ...] = ()
    longhand_of: CssPropertyId | None = None
    affects_visibility: bool = False
    affects_paint_order: bool = False


def _spec(
    property_id: CssPropertyId,
    *categories: CssPropertyCategory,
    color_role: CssColorRole | None = None,
    computed_aliases: tuple[str, ...] = (),
    shorthand_for: tuple[CssPropertyId, ...] = (),
    longhand_of: CssPropertyId | None = None,
    affects_visibility: bool = False,
    affects_paint_order: bool = False,
) -> CssPropertySpec:
    return CssPropertySpec(
        property_id=property_id,
        categories=categories,
        color_role=color_role,
        computed_aliases=computed_aliases,
        shorthand_for=shorthand_for,
        longhand_of=longhand_of,
        affects_visibility=affects_visibility,
        affects_paint_order=affects_paint_order,
    )


CSS_PROPERTY_SPECS: tuple[CssPropertySpec, ...] = (
    _spec(CssPropertyId.DISPLAY, CssPropertyCategory.DISPLAY, affects_visibility=True),
    _spec(CssPropertyId.VISIBILITY, CssPropertyCategory.DISPLAY, affects_visibility=True),
    _spec(CssPropertyId.OPACITY, CssPropertyCategory.EFFECT, computed_aliases=("opacity",), affects_visibility=True),
    _spec(CssPropertyId.POSITION, CssPropertyCategory.POSITION, affects_paint_order=True),
    _spec(CssPropertyId.Z_INDEX, CssPropertyCategory.POSITION, affects_paint_order=True),
    _spec(CssPropertyId.WIDTH, CssPropertyCategory.DISPLAY),
    _spec(CssPropertyId.HEIGHT, CssPropertyCategory.DISPLAY),
    _spec(CssPropertyId.COLOR, CssPropertyCategory.COLOR, color_role=CssColorRole.FOREGROUND, computed_aliases=("color", "currentColor"), affects_visibility=True),
    _spec(CssPropertyId.ACCENT_COLOR, CssPropertyCategory.COLOR, color_role=CssColorRole.FOREGROUND, affects_visibility=True),
    _spec(
        CssPropertyId.BACKGROUND,
        CssPropertyCategory.BACKGROUND,
        color_role=CssColorRole.BACKGROUND,
        shorthand_for=(
            CssPropertyId.BACKGROUND_COLOR,
            CssPropertyId.BACKGROUND_IMAGE,
            CssPropertyId.BACKGROUND_REPEAT,
            CssPropertyId.BACKGROUND_POSITION,
            CssPropertyId.BACKGROUND_SIZE,
            CssPropertyId.BACKGROUND_ATTACHMENT,
            CssPropertyId.BACKGROUND_CLIP,
            CssPropertyId.BACKGROUND_ORIGIN,
        ),
        affects_visibility=True,
    ),
    _spec(CssPropertyId.BACKGROUND_COLOR, CssPropertyCategory.BACKGROUND, color_role=CssColorRole.BACKGROUND, computed_aliases=("backgroundColor",), longhand_of=CssPropertyId.BACKGROUND, affects_visibility=True),
    _spec(CssPropertyId.BACKGROUND_IMAGE, CssPropertyCategory.BACKGROUND, computed_aliases=("backgroundImage",), longhand_of=CssPropertyId.BACKGROUND, affects_visibility=True),
    _spec(CssPropertyId.BACKGROUND_REPEAT, CssPropertyCategory.BACKGROUND, computed_aliases=("backgroundRepeat",), longhand_of=CssPropertyId.BACKGROUND),
    _spec(CssPropertyId.BACKGROUND_POSITION, CssPropertyCategory.BACKGROUND, computed_aliases=("backgroundPosition",), longhand_of=CssPropertyId.BACKGROUND),
    _spec(CssPropertyId.BACKGROUND_SIZE, CssPropertyCategory.BACKGROUND, computed_aliases=("backgroundSize",), longhand_of=CssPropertyId.BACKGROUND),
    _spec(CssPropertyId.BACKGROUND_ATTACHMENT, CssPropertyCategory.BACKGROUND, computed_aliases=("backgroundAttachment",), longhand_of=CssPropertyId.BACKGROUND),
    _spec(CssPropertyId.BACKGROUND_CLIP, CssPropertyCategory.BACKGROUND, computed_aliases=("backgroundClip",), longhand_of=CssPropertyId.BACKGROUND),
    _spec(CssPropertyId.BACKGROUND_ORIGIN, CssPropertyCategory.BACKGROUND, computed_aliases=("backgroundOrigin",), longhand_of=CssPropertyId.BACKGROUND),
    _spec(CssPropertyId.BORDER, CssPropertyCategory.BORDER, shorthand_for=(CssPropertyId.BORDER_COLOR, CssPropertyId.BORDER_STYLE, CssPropertyId.BORDER_WIDTH), affects_visibility=True),
    _spec(CssPropertyId.BORDER_COLOR, CssPropertyCategory.BORDER, color_role=CssColorRole.FOREGROUND, computed_aliases=("borderColor",), longhand_of=CssPropertyId.BORDER, shorthand_for=(CssPropertyId.BORDER_TOP_COLOR, CssPropertyId.BORDER_RIGHT_COLOR, CssPropertyId.BORDER_BOTTOM_COLOR, CssPropertyId.BORDER_LEFT_COLOR, CssPropertyId.BORDER_BLOCK_START_COLOR, CssPropertyId.BORDER_BLOCK_END_COLOR, CssPropertyId.BORDER_INLINE_START_COLOR), affects_visibility=True),
    _spec(CssPropertyId.BORDER_STYLE, CssPropertyCategory.BORDER, computed_aliases=("borderStyle",), longhand_of=CssPropertyId.BORDER, affects_visibility=True),
    _spec(CssPropertyId.BORDER_WIDTH, CssPropertyCategory.BORDER, computed_aliases=("borderWidth",), longhand_of=CssPropertyId.BORDER, affects_visibility=True),
    _spec(CssPropertyId.BORDER_TOP, CssPropertyCategory.BORDER, affects_visibility=True),
    _spec(CssPropertyId.BORDER_RIGHT, CssPropertyCategory.BORDER, affects_visibility=True),
    _spec(CssPropertyId.BORDER_BOTTOM, CssPropertyCategory.BORDER, affects_visibility=True),
    _spec(CssPropertyId.BORDER_LEFT, CssPropertyCategory.BORDER, affects_visibility=True),
    _spec(CssPropertyId.BORDER_BLOCK_START, CssPropertyCategory.BORDER, affects_visibility=True),
    _spec(CssPropertyId.BORDER_BLOCK_END, CssPropertyCategory.BORDER, affects_visibility=True),
    _spec(CssPropertyId.BORDER_INLINE_START, CssPropertyCategory.BORDER, affects_visibility=True),
    _spec(CssPropertyId.BORDER_INLINE_END, CssPropertyCategory.BORDER, affects_visibility=True),
    _spec(CssPropertyId.BORDER_TOP_COLOR, CssPropertyCategory.BORDER, color_role=CssColorRole.FOREGROUND, computed_aliases=("borderTopColor",), longhand_of=CssPropertyId.BORDER_COLOR, affects_visibility=True),
    _spec(CssPropertyId.BORDER_RIGHT_COLOR, CssPropertyCategory.BORDER, color_role=CssColorRole.FOREGROUND, computed_aliases=("borderRightColor",), longhand_of=CssPropertyId.BORDER_COLOR, affects_visibility=True),
    _spec(CssPropertyId.BORDER_BOTTOM_COLOR, CssPropertyCategory.BORDER, color_role=CssColorRole.FOREGROUND, computed_aliases=("borderBottomColor",), longhand_of=CssPropertyId.BORDER_COLOR, affects_visibility=True),
    _spec(CssPropertyId.BORDER_LEFT_COLOR, CssPropertyCategory.BORDER, color_role=CssColorRole.FOREGROUND, computed_aliases=("borderLeftColor",), longhand_of=CssPropertyId.BORDER_COLOR, affects_visibility=True),
    _spec(CssPropertyId.BORDER_BLOCK_START_COLOR, CssPropertyCategory.BORDER, color_role=CssColorRole.FOREGROUND, computed_aliases=("borderBlockStartColor",), longhand_of=CssPropertyId.BORDER_COLOR, affects_visibility=True),
    _spec(CssPropertyId.BORDER_BLOCK_END_COLOR, CssPropertyCategory.BORDER, color_role=CssColorRole.FOREGROUND, computed_aliases=("borderBlockEndColor",), longhand_of=CssPropertyId.BORDER_COLOR, affects_visibility=True),
    _spec(CssPropertyId.BORDER_INLINE_START_COLOR, CssPropertyCategory.BORDER, color_role=CssColorRole.FOREGROUND, computed_aliases=("borderInlineStartColor",), longhand_of=CssPropertyId.BORDER_COLOR, affects_visibility=True),
    _spec(CssPropertyId.BORDER_RADIUS, CssPropertyCategory.BORDER, CssPropertyCategory.APPEARANCE, affects_visibility=True),
    _spec(CssPropertyId.OUTLINE, CssPropertyCategory.BORDER, shorthand_for=(CssPropertyId.OUTLINE_COLOR, CssPropertyId.OUTLINE_STYLE, CssPropertyId.OUTLINE_WIDTH), affects_visibility=True),
    _spec(CssPropertyId.OUTLINE_COLOR, CssPropertyCategory.BORDER, color_role=CssColorRole.FOREGROUND, computed_aliases=("outlineColor",), longhand_of=CssPropertyId.OUTLINE, affects_visibility=True),
    _spec(CssPropertyId.OUTLINE_STYLE, CssPropertyCategory.BORDER, computed_aliases=("outlineStyle",), longhand_of=CssPropertyId.OUTLINE, affects_visibility=True),
    _spec(CssPropertyId.OUTLINE_WIDTH, CssPropertyCategory.BORDER, computed_aliases=("outlineWidth",), longhand_of=CssPropertyId.OUTLINE, affects_visibility=True),
    _spec(CssPropertyId.OUTLINE_OFFSET, CssPropertyCategory.BORDER, affects_visibility=True),
    _spec(CssPropertyId.TEXT_DECORATION, CssPropertyCategory.DECORATION, shorthand_for=(CssPropertyId.TEXT_DECORATION_COLOR, CssPropertyId.TEXT_DECORATION_LINE, CssPropertyId.TEXT_DECORATION_STYLE, CssPropertyId.TEXT_DECORATION_THICKNESS), affects_visibility=True),
    _spec(CssPropertyId.TEXT_DECORATION_COLOR, CssPropertyCategory.DECORATION, color_role=CssColorRole.FOREGROUND, computed_aliases=("textDecorationColor",), longhand_of=CssPropertyId.TEXT_DECORATION, affects_visibility=True),
    _spec(CssPropertyId.TEXT_DECORATION_LINE, CssPropertyCategory.DECORATION, longhand_of=CssPropertyId.TEXT_DECORATION, affects_visibility=True),
    _spec(CssPropertyId.TEXT_DECORATION_STYLE, CssPropertyCategory.DECORATION, longhand_of=CssPropertyId.TEXT_DECORATION, affects_visibility=True),
    _spec(CssPropertyId.TEXT_DECORATION_THICKNESS, CssPropertyCategory.DECORATION, longhand_of=CssPropertyId.TEXT_DECORATION, affects_visibility=True),
    _spec(CssPropertyId.TEXT_EMPHASIS, CssPropertyCategory.DECORATION, shorthand_for=(CssPropertyId.TEXT_EMPHASIS_COLOR,), affects_visibility=True),
    _spec(CssPropertyId.TEXT_EMPHASIS_COLOR, CssPropertyCategory.DECORATION, color_role=CssColorRole.FOREGROUND, computed_aliases=("textEmphasisColor",), longhand_of=CssPropertyId.TEXT_EMPHASIS, affects_visibility=True),
    _spec(CssPropertyId.TEXT_SHADOW, CssPropertyCategory.DECORATION, computed_aliases=("textShadow",), affects_visibility=True),
    _spec(CssPropertyId.BOX_SHADOW, CssPropertyCategory.EFFECT, computed_aliases=("boxShadow",), affects_visibility=True),
    _spec(CssPropertyId.FILTER, CssPropertyCategory.EFFECT, affects_visibility=True),
    _spec(CssPropertyId.CARET, CssPropertyCategory.COLOR, color_role=CssColorRole.FOREGROUND, shorthand_for=(CssPropertyId.CARET_COLOR,), affects_visibility=True),
    _spec(CssPropertyId.CARET_COLOR, CssPropertyCategory.COLOR, color_role=CssColorRole.FOREGROUND, computed_aliases=("caretColor",), longhand_of=CssPropertyId.CARET, affects_visibility=True),
    _spec(CssPropertyId.COLUMN_RULE, CssPropertyCategory.BORDER, shorthand_for=(CssPropertyId.COLUMN_RULE_COLOR,), affects_visibility=True),
    _spec(CssPropertyId.COLUMN_RULE_COLOR, CssPropertyCategory.BORDER, color_role=CssColorRole.FOREGROUND, computed_aliases=("columnRuleColor",), longhand_of=CssPropertyId.COLUMN_RULE, affects_visibility=True),
    _spec(CssPropertyId.APPEARANCE, CssPropertyCategory.APPEARANCE),
    _spec(CssPropertyId.OBJECT_FIT, CssPropertyCategory.APPEARANCE),
    _spec(CssPropertyId.OBJECT_POSITION, CssPropertyCategory.APPEARANCE),
    _spec(CssPropertyId.FILL, CssPropertyCategory.COLOR, color_role=CssColorRole.FOREGROUND, affects_visibility=True),
    _spec(CssPropertyId.FILL_OPACITY, CssPropertyCategory.COLOR, affects_visibility=True),
    _spec(CssPropertyId.FILL_RULE, CssPropertyCategory.COLOR, affects_visibility=True),
    _spec(CssPropertyId.STROKE, CssPropertyCategory.COLOR, color_role=CssColorRole.FOREGROUND, affects_visibility=True),
    _spec(CssPropertyId.STROKE_OPACITY, CssPropertyCategory.COLOR, affects_visibility=True),
    _spec(CssPropertyId.STOP_COLOR, CssPropertyCategory.COLOR, color_role=CssColorRole.OTHER, affects_visibility=True),
    _spec(CssPropertyId.FLOOD_COLOR, CssPropertyCategory.COLOR, color_role=CssColorRole.OTHER, affects_visibility=True),
    _spec(CssPropertyId.LIGHTING_COLOR, CssPropertyCategory.COLOR, color_role=CssColorRole.OTHER, affects_visibility=True),
)


CSS_PROPERTIES_BY_ID: Mapping[str, CssPropertySpec] = {
    spec.property_id.value: spec for spec in CSS_PROPERTY_SPECS
}

CSS_PROPERTY_COMPUTED_ALIASES: Mapping[str, str] = {
    alias: spec.property_id.value
    for spec in CSS_PROPERTY_SPECS
    for alias in spec.computed_aliases
}

CSS_PROPERTY_SHORTHANDS: Mapping[str, tuple[str, ...]] = {
    spec.property_id.value: tuple(item.value for item in spec.shorthand_for)
    for spec in CSS_PROPERTY_SPECS
    if spec.shorthand_for
}


def get_in_scope_css_properties() -> tuple[CssPropertySpec, ...]:
    return CSS_PROPERTY_SPECS
