from collections.abc import Mapping
from enum import StrEnum
import re


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


_CSS_WORD_BOUNDARY_1 = re.compile(r"([a-z0-9])([A-Z])")
_CSS_WORD_BOUNDARY_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CSS_SEPARATORS = re.compile(r"[-_\s]+")
def _normalize_css_property_name(value: object) -> str:
    name = str(value or "").strip()
    if not name:
        return ""
    name = _CSS_WORD_BOUNDARY_2.sub(r"\1-\2", name)
    name = _CSS_WORD_BOUNDARY_1.sub(r"\1-\2", name)
    name = _CSS_SEPARATORS.sub("-", name)
    return name.strip("-").lower()

class CssPropertyId(StrEnum):
    categories: tuple[CssPropertyCategory, ...]
    color_role: CssColorRole | None
    _shorthand_names: tuple[str, ...]
    _longhand_name: str | None
    shorthand_for: tuple["CssPropertyId", ...]
    longhand_of: "CssPropertyId | None"
    affects_visibility: bool
    affects_paint_order: bool

    def __new__(
        cls,
        value: str,
        categories: tuple[CssPropertyCategory, ...],
        color_role: CssColorRole | None = None,
        shorthand_for: tuple[str, ...] = (),
        longhand_of: str | None = None,
        affects_visibility: bool = False,
        affects_paint_order: bool = False,
    ) -> "CssPropertyId":
        self = str.__new__(cls, value)
        self._value_ = value
        return self

    def __init__(
        self,
        value: str,
        categories: tuple[CssPropertyCategory, ...],
        color_role: CssColorRole | None = None,
        shorthand_for: tuple[str, ...] = (),
        longhand_of: str | None = None,
        affects_visibility: bool = False,
        affects_paint_order: bool = False,
    ) -> None:
        self.categories = categories
        self.color_role = color_role
        self._shorthand_names = shorthand_for
        self._longhand_name = longhand_of
        self.shorthand_for = ()
        self.longhand_of = None
        self.affects_visibility = affects_visibility
        self.affects_paint_order = affects_paint_order

    ACCENT_COLOR = (
        'accent-color',
        (CssPropertyCategory.COLOR,),
        CssColorRole.FOREGROUND,
        (),
        None,
        True,
        False,
    )
    APPEARANCE = (
        'appearance',
        (CssPropertyCategory.APPEARANCE,),
        None,
        (),
        None,
        False,
        False,
    )
    BACKGROUND = (
        'background',
        (CssPropertyCategory.BACKGROUND,),
        CssColorRole.BACKGROUND,
        ('BACKGROUND_COLOR', 'BACKGROUND_IMAGE', 'BACKGROUND_REPEAT', 'BACKGROUND_POSITION', 'BACKGROUND_SIZE', 'BACKGROUND_ATTACHMENT', 'BACKGROUND_CLIP', 'BACKGROUND_ORIGIN'),
        None,
        True,
        False,
    )
    BACKGROUND_ATTACHMENT = (
        'background-attachment',
        (CssPropertyCategory.BACKGROUND,),
        None,
        (),
        'BACKGROUND',
        False,
        False,
    )
    BACKGROUND_CLIP = (
        'background-clip',
        (CssPropertyCategory.BACKGROUND,),
        None,
        (),
        'BACKGROUND',
        False,
        False,
    )
    BACKGROUND_COLOR = (
        'background-color',
        (CssPropertyCategory.BACKGROUND,),
        CssColorRole.BACKGROUND,
        (),
        'BACKGROUND',
        True,
        False,
    )
    BACKGROUND_IMAGE = (
        'background-image',
        (CssPropertyCategory.BACKGROUND,),
        None,
        (),
        'BACKGROUND',
        True,
        False,
    )
    BACKGROUND_ORIGIN = (
        'background-origin',
        (CssPropertyCategory.BACKGROUND,),
        None,
        (),
        'BACKGROUND',
        False,
        False,
    )
    BACKGROUND_POSITION = (
        'background-position',
        (CssPropertyCategory.BACKGROUND,),
        None,
        (),
        'BACKGROUND',
        False,
        False,
    )
    BACKGROUND_REPEAT = (
        'background-repeat',
        (CssPropertyCategory.BACKGROUND,),
        None,
        (),
        'BACKGROUND',
        False,
        False,
    )
    BACKGROUND_SIZE = (
        'background-size',
        (CssPropertyCategory.BACKGROUND,),
        None,
        (),
        'BACKGROUND',
        False,
        False,
    )
    BORDER = (
        'border',
        (CssPropertyCategory.BORDER,),
        None,
        ('BORDER_COLOR', 'BORDER_STYLE', 'BORDER_WIDTH'),
        None,
        True,
        False,
    )
    BORDER_BLOCK_END = (
        'border-block-end',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        None,
        True,
        False,
    )
    BORDER_BLOCK_END_COLOR = (
        'border-block-end-color',
        (CssPropertyCategory.BORDER,),
        CssColorRole.FOREGROUND,
        (),
        'BORDER_COLOR',
        True,
        False,
    )
    BORDER_BLOCK_START = (
        'border-block-start',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        None,
        True,
        False,
    )
    BORDER_BLOCK_START_COLOR = (
        'border-block-start-color',
        (CssPropertyCategory.BORDER,),
        CssColorRole.FOREGROUND,
        (),
        'BORDER_COLOR',
        True,
        False,
    )
    BORDER_BOTTOM = (
        'border-bottom',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        None,
        True,
        False,
    )
    BORDER_BOTTOM_COLOR = (
        'border-bottom-color',
        (CssPropertyCategory.BORDER,),
        CssColorRole.FOREGROUND,
        (),
        'BORDER_COLOR',
        True,
        False,
    )
    BORDER_COLOR = (
        'border-color',
        (CssPropertyCategory.BORDER,),
        CssColorRole.FOREGROUND,
        ('BORDER_TOP_COLOR', 'BORDER_RIGHT_COLOR', 'BORDER_BOTTOM_COLOR', 'BORDER_LEFT_COLOR', 'BORDER_BLOCK_START_COLOR', 'BORDER_BLOCK_END_COLOR', 'BORDER_INLINE_START_COLOR'),
        'BORDER',
        True,
        False,
    )
    BORDER_INLINE_END = (
        'border-inline-end',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        None,
        True,
        False,
    )
    BORDER_INLINE_START = (
        'border-inline-start',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        None,
        True,
        False,
    )
    BORDER_INLINE_START_COLOR = (
        'border-inline-start-color',
        (CssPropertyCategory.BORDER,),
        CssColorRole.FOREGROUND,
        (),
        'BORDER_COLOR',
        True,
        False,
    )
    BORDER_LEFT = (
        'border-left',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        None,
        True,
        False,
    )
    BORDER_LEFT_COLOR = (
        'border-left-color',
        (CssPropertyCategory.BORDER,),
        CssColorRole.FOREGROUND,
        (),
        'BORDER_COLOR',
        True,
        False,
    )
    BORDER_RADIUS = (
        'border-radius',
        (CssPropertyCategory.BORDER, CssPropertyCategory.APPEARANCE),
        None,
        (),
        None,
        True,
        False,
    )
    BORDER_RIGHT = (
        'border-right',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        None,
        True,
        False,
    )
    BORDER_RIGHT_COLOR = (
        'border-right-color',
        (CssPropertyCategory.BORDER,),
        CssColorRole.FOREGROUND,
        (),
        'BORDER_COLOR',
        True,
        False,
    )
    BORDER_STYLE = (
        'border-style',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        'BORDER',
        True,
        False,
    )
    BORDER_TOP = (
        'border-top',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        None,
        True,
        False,
    )
    BORDER_TOP_COLOR = (
        'border-top-color',
        (CssPropertyCategory.BORDER,),
        CssColorRole.FOREGROUND,
        (),
        'BORDER_COLOR',
        True,
        False,
    )
    BORDER_WIDTH = (
        'border-width',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        'BORDER',
        True,
        False,
    )
    BOX_SHADOW = (
        'box-shadow',
        (CssPropertyCategory.EFFECT,),
        None,
        (),
        None,
        True,
        False,
    )
    CARET = (
        'caret',
        (CssPropertyCategory.COLOR,),
        CssColorRole.FOREGROUND,
        ('CARET_COLOR',),
        None,
        True,
        False,
    )
    CARET_COLOR = (
        'caret-color',
        (CssPropertyCategory.COLOR,),
        CssColorRole.FOREGROUND,
        (),
        'CARET',
        True,
        False,
    )
    COLOR = (
        'color',
        (CssPropertyCategory.COLOR,),
        CssColorRole.FOREGROUND,
        (),
        None,
        True,
        False,
    )
    COLUMN_RULE = (
        'column-rule',
        (CssPropertyCategory.BORDER,),
        None,
        ('COLUMN_RULE_COLOR',),
        None,
        True,
        False,
    )
    COLUMN_RULE_COLOR = (
        'column-rule-color',
        (CssPropertyCategory.BORDER,),
        CssColorRole.FOREGROUND,
        (),
        'COLUMN_RULE',
        True,
        False,
    )
    DISPLAY = (
        'display',
        (CssPropertyCategory.DISPLAY,),
        None,
        (),
        None,
        True,
        False,
    )
    FILL = (
        'fill',
        (CssPropertyCategory.COLOR,),
        CssColorRole.FOREGROUND,
        (),
        None,
        True,
        False,
    )
    FILL_OPACITY = (
        'fill-opacity',
        (CssPropertyCategory.COLOR,),
        None,
        (),
        None,
        True,
        False,
    )
    FILL_RULE = (
        'fill-rule',
        (CssPropertyCategory.COLOR,),
        None,
        (),
        None,
        True,
        False,
    )
    FILTER = (
        'filter',
        (CssPropertyCategory.EFFECT,),
        None,
        (),
        None,
        True,
        False,
    )
    FLOOD_COLOR = (
        'flood-color',
        (CssPropertyCategory.COLOR,),
        CssColorRole.OTHER,
        (),
        None,
        True,
        False,
    )
    HEIGHT = (
        'height',
        (CssPropertyCategory.DISPLAY,),
        None,
        (),
        None,
        False,
        False,
    )
    LIGHTING_COLOR = (
        'lighting-color',
        (CssPropertyCategory.COLOR,),
        CssColorRole.OTHER,
        (),
        None,
        True,
        False,
    )
    OBJECT_FIT = (
        'object-fit',
        (CssPropertyCategory.APPEARANCE,),
        None,
        (),
        None,
        False,
        False,
    )
    OBJECT_POSITION = (
        'object-position',
        (CssPropertyCategory.APPEARANCE,),
        None,
        (),
        None,
        False,
        False,
    )
    OPACITY = (
        'opacity',
        (CssPropertyCategory.EFFECT,),
        None,
        (),
        None,
        True,
        False,
    )
    OUTLINE = (
        'outline',
        (CssPropertyCategory.BORDER,),
        None,
        ('OUTLINE_COLOR', 'OUTLINE_STYLE', 'OUTLINE_WIDTH'),
        None,
        True,
        False,
    )
    OUTLINE_COLOR = (
        'outline-color',
        (CssPropertyCategory.BORDER,),
        CssColorRole.FOREGROUND,
        (),
        'OUTLINE',
        True,
        False,
    )
    OUTLINE_OFFSET = (
        'outline-offset',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        None,
        True,
        False,
    )
    OUTLINE_STYLE = (
        'outline-style',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        'OUTLINE',
        True,
        False,
    )
    OUTLINE_WIDTH = (
        'outline-width',
        (CssPropertyCategory.BORDER,),
        None,
        (),
        'OUTLINE',
        True,
        False,
    )
    POSITION = (
        'position',
        (CssPropertyCategory.POSITION,),
        None,
        (),
        None,
        False,
        True,
    )
    STOP_COLOR = (
        'stop-color',
        (CssPropertyCategory.COLOR,),
        CssColorRole.OTHER,
        (),
        None,
        True,
        False,
    )
    STROKE = (
        'stroke',
        (CssPropertyCategory.COLOR,),
        CssColorRole.FOREGROUND,
        (),
        None,
        True,
        False,
    )
    STROKE_OPACITY = (
        'stroke-opacity',
        (CssPropertyCategory.COLOR,),
        None,
        (),
        None,
        True,
        False,
    )
    TEXT_DECORATION = (
        'text-decoration',
        (CssPropertyCategory.DECORATION,),
        None,
        ('TEXT_DECORATION_COLOR', 'TEXT_DECORATION_LINE', 'TEXT_DECORATION_STYLE', 'TEXT_DECORATION_THICKNESS'),
        None,
        True,
        False,
    )
    TEXT_DECORATION_COLOR = (
        'text-decoration-color',
        (CssPropertyCategory.DECORATION,),
        CssColorRole.FOREGROUND,
        (),
        'TEXT_DECORATION',
        True,
        False,
    )
    TEXT_DECORATION_LINE = (
        'text-decoration-line',
        (CssPropertyCategory.DECORATION,),
        None,
        (),
        'TEXT_DECORATION',
        True,
        False,
    )
    TEXT_DECORATION_STYLE = (
        'text-decoration-style',
        (CssPropertyCategory.DECORATION,),
        None,
        (),
        'TEXT_DECORATION',
        True,
        False,
    )
    TEXT_DECORATION_THICKNESS = (
        'text-decoration-thickness',
        (CssPropertyCategory.DECORATION,),
        None,
        (),
        'TEXT_DECORATION',
        True,
        False,
    )
    TEXT_EMPHASIS = (
        'text-emphasis',
        (CssPropertyCategory.DECORATION,),
        None,
        ('TEXT_EMPHASIS_COLOR',),
        None,
        True,
        False,
    )
    TEXT_EMPHASIS_COLOR = (
        'text-emphasis-color',
        (CssPropertyCategory.DECORATION,),
        CssColorRole.FOREGROUND,
        (),
        'TEXT_EMPHASIS',
        True,
        False,
    )
    TEXT_SHADOW = (
        'text-shadow',
        (CssPropertyCategory.DECORATION,),
        None,
        (),
        None,
        True,
        False,
    )
    VISIBILITY = (
        'visibility',
        (CssPropertyCategory.DISPLAY,),
        None,
        (),
        None,
        True,
        False,
    )
    WIDTH = (
        'width',
        (CssPropertyCategory.DISPLAY,),
        None,
        (),
        None,
        False,
        False,
    )
    Z_INDEX = (
        'z-index',
        (CssPropertyCategory.POSITION,),
        None,
        (),
        None,
        False,
        True,
    )


for spec in CssPropertyId:
    spec.shorthand_for = tuple(CssPropertyId[name] for name in spec._shorthand_names)
    spec.longhand_of = CssPropertyId[spec._longhand_name] if spec._longhand_name is not None else None


CSS_PROPERTY_SPECS: tuple[CssPropertyId, ...] = tuple(CssPropertyId)
_CSS_PROPERTY_CANONICAL_BY_ID: dict[str, CssPropertyId] = {spec.value: spec for spec in CSS_PROPERTY_SPECS}

CSS_PROPERTIES_BY_ID: Mapping[str, CssPropertyId] = _CSS_PROPERTY_CANONICAL_BY_ID

CSS_PROPERTY_SHORTHANDS: Mapping[str, tuple[str, ...]] = {
    spec.value: tuple(item.value for item in spec.shorthand_for)
    for spec in CSS_PROPERTY_SPECS
    if spec.shorthand_for
}


def get_css_property(value: object) -> CssPropertyId | None:
    normalized = _normalize_css_property_name(value)
    if not normalized:
        return None
    return CSS_PROPERTIES_BY_ID.get(normalized)


def get_in_scope_css_properties() -> tuple[CssPropertyId, ...]:
    return CSS_PROPERTY_SPECS
