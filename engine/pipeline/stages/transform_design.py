from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.data.scope_css import CSSPROPERTIES, CSSDATA
from engine.domain.data.scope_html_elements import get_html_element_category
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import Color, ColorScheme, Palette
from engine.domain.models.element import Element, Property
from engine.domain.models.session import Session
from engine.domain.models.summary import Summary
from engine.domain.utils.parsers import is_gradient, is_url_image, replace_property_values
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


_MAIN_SURFACE_CATEGORY = "main-surface"
_CONTAINER_CATEGORY = "container"
_INPUT_CATEGORY = "input"
_MEDIA_CATEGORY = "media"
_FORCED_MAIN_SURFACE_TAGS = {"html", "body", "main"}
_CONTENT_CATEGORIES = {
    "composed",
    "other",
    "decoration",
    "typography",
}
_BACKGROUND_ROLE = "background"
_FOREGROUND_ROLE = "foreground"
_NEUTRAL_PALETTE_NAME = "Neutral"
_MAIN_SURFACE_COLOR = Color("rgb(0, 0, 0)")
_TEXT_CONTRAST_RATIO = 4.5
_LARGE_TEXT_CONTRAST_RATIO = 3.0
_NON_TEXT_CONTRAST_RATIO = 3.0
_LIGHT_BACKGROUND_TONE = 55.0
_OPAQUE_ALPHA = 0.999

_CONTAINER_BACKGROUND_TONES = (10, 20, 30)
_CONTENT_BACKGROUND_TONES = (20, 30)
_INPUT_BACKGROUND_TONE = 20
_SHADOW_TONE = 0
_LIGHT_FOREGROUND_TONES = (100, 95, 90, 80, 70, 60, 50)
_DARK_FOREGROUND_TONES = (0, 10, 20, 30, 40, 50)
_MUTED_FOREGROUND_DARK_BG_TONES = (60, 50, 70, 40)
_MUTED_FOREGROUND_LIGHT_BG_TONES = (40, 30, 50, 20)
_MUTED_FOREGROUND_MIN_CONTRAST = 2.0


@dataclass(frozen=True, slots=True)
class _ColorToken:
    text: str
    color: Color


CONTRACT = StageContract(
    name="transform_design",
    requires=(
        context_value(K.SESSION, Session),
        context_value(K.PAGE_BUILDER, PageBuilder),
        context_value(K.DOM_TREE, Element),
        context_value(K.COLOR_SCHEME, ColorScheme),
        context_value(K.SUMMARY, Summary),
    ),
    produces=(
        context_value(K.DOM_TREE, Element),
        context_value(K.SUMMARY, Summary),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    session = context.get(K.SESSION)
    page_builder = context.get(K.PAGE_BUILDER)
    root = context.get(K.DOM_TREE)
    color_scheme = context.get(K.COLOR_SCHEME)
    summary = context.get(K.SUMMARY)

    context.trace.add_stage_event(CONTRACT.name, "start")

    page_builder.set_color_scheme()

    background_changes = _transform_backgrounds(
        root,
        page_builder,
        color_scheme,
        summary,
    )
    foreground_changes = _transform_foregrounds(
        root,
        page_builder,
        color_scheme,
        summary,
    )

    after_screenshot = session.get_path("after.png", "artifacts", "png")
    after_screenshot_path = page_builder.capture_fullpage_screenshot(output_path=after_screenshot)

    context.set(K.DOM_TREE, root)
    context.set(K.SUMMARY, summary)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "after_screenshot_path": after_screenshot_path,
            "background_changes": background_changes,
            "foreground_changes": foreground_changes,
        },
    )
    return context


def _transform_backgrounds(
    root: Element,
    page_builder: PageBuilder,
    color_scheme: ColorScheme,
    summary: Summary,
) -> int:
    change_count = 0

    for element, surface_depth in _iter_bfs_with_surface_depth(root):
        category = _element_category(element)
        if not category or category == _MEDIA_CATEGORY:
            continue

        forced_surface = _is_forced_main_surface(element, category)
        if forced_surface:
            change_count += _force_main_surface(
                element,
                page_builder,
                summary,
            )

        for css_property in tuple(element.properties):
            css_data = _css_data_for(css_property)
            property_name = str(css_property.name or "").strip().lower()
            if (
                css_data is None
                or css_data.role != _BACKGROUND_ROLE
                or not css_property.has_color
                or not _property_applies_to_category(css_data, category)
                or forced_surface and property_name == "background-color"
                or _skip_color_property(css_property)
            ):
                continue

            target_colors = _transform_background_tokens(
                css_property,
                _MAIN_SURFACE_CATEGORY if forced_surface else category,
                surface_depth,
                color_scheme,
            )
            change_count += _apply_transformed_property(
                page_builder,
                summary,
                element,
                css_property,
                target_colors,
            )

    return change_count


def _transform_foregrounds(
    root: Element,
    page_builder: PageBuilder,
    color_scheme: ColorScheme,
    summary: Summary,
) -> int:
    change_count = 0

    for element in root.iter_bfs():
        category = _element_category(element)
        if not category or category == _MEDIA_CATEGORY:
            continue

        for css_property in tuple(element.properties):
            css_data = _css_data_for(css_property)
            if (
                css_data is None
                or css_data.role != _FOREGROUND_ROLE
                or not css_property.has_color
                or not _property_applies_to_category(css_data, category)
                or _skip_color_property(css_property)
            ):
                continue

            target_colors = _transform_foreground_tokens(
                element,
                css_property,
                category,
                page_builder,
                color_scheme,
            )
            change_count += _apply_transformed_property(
                page_builder,
                summary,
                element,
                css_property,
                target_colors,
            )

    return change_count


def _transform_background_tokens(
    css_property: Property,
    category: str,
    surface_depth: int,
    color_scheme: ColorScheme,
) -> list[Color]:
    tokens = _find_color_tokens(css_property.value)
    transformed: list[Color] = []

    for token in tokens:
        target_tone = _background_target_tone(
            token.color,
            category,
            surface_depth,
        )
        force_neutral = category in {
            _MAIN_SURFACE_CATEGORY,
            _CONTAINER_CATEGORY,
            _INPUT_CATEGORY,
        } and _is_achromatic(token.color)
        transformed.append(
            _select_tonal_color(
                color_scheme,
                token.color,
                target_tone,
                force_neutral=force_neutral,
            )
        )

    return transformed


def _transform_foreground_tokens(
    element: Element,
    css_property: Property,
    category: str,
    page_builder: PageBuilder,
    color_scheme: ColorScheme,
) -> list[Color]:
    tokens = _find_color_tokens(css_property.value)
    property_name = str(css_property.name or "").strip().lower()

    if _is_shadow_property(css_property.name):
        return [
            _select_tonal_color(
                color_scheme,
                token.color,
                _SHADOW_TONE,
                force_neutral=True,
            )
            for token in tokens
        ]

    backgrounds = _background_colors_for(page_builder, element)

    if _is_border_property(css_property.name):
        return [
            _select_visible_muted_color(
                color_scheme,
                token.color,
                backgrounds,
            )
            for token in tokens
        ]

    if property_name != "color":
        return [
            _select_muted_foreground_color(
                color_scheme,
                token.color,
                backgrounds,
            )
            for token in tokens
        ]

    required_ratio = _required_contrast_ratio(
        page_builder,
        element,
        category,
        css_property.name,
    )
    prefer_light = not _has_light_background(backgrounds)

    return [
        _select_contrast_color(
            color_scheme,
            token.color,
            backgrounds,
            required_ratio,
            prefer_light=prefer_light,
        )
        for token in tokens
    ]


def _force_main_surface(
    element: Element,
    page_builder: PageBuilder,
    summary: Summary,
) -> int:
    if not element.node_id:
        return 0

    current_property = element.property("background-color")
    before_value = current_property.value if current_property is not None else ""
    after_value = _serialize_color(_MAIN_SURFACE_COLOR)

    if before_value == after_value:
        return 0

    page_builder.set_effective_value(
        element.node_id,
        "background-color",
        after_value,
    )
    _upsert_property(
        element,
        "background-color",
        after_value,
        has_color=True,
    )

    before_color = _first_color(before_value)
    if before_color is not None:
        _record_change(
            summary,
            before_value,
            after_value,
            before_color,
            _MAIN_SURFACE_COLOR,
        )
    return 1


def _apply_transformed_property(
    page_builder: PageBuilder,
    summary: Summary,
    element: Element,
    css_property: Property,
    target_colors: list[Color],
) -> int:
    tokens = _find_color_tokens(css_property.value)
    if not tokens or len(tokens) != len(target_colors):
        return 0

    changed_pairs = [
        (token, target)
        for token, target in zip(tokens, target_colors)
        if not _same_color(token.color, target)
    ]
    if not changed_pairs:
        return 0

    before_value = css_property.value
    try:
        after_value = _transform_property_value(
            before_value,
            tokens,
            target_colors,
        )
    except (TypeError, ValueError):
        return 0

    if before_value == after_value or not element.node_id:
        return 0

    page_builder.set_effective_value(
        element.node_id,
        css_property.name,
        after_value,
    )
    css_property.value = after_value

    for token, target in changed_pairs:
        _record_change(
            summary,
            before_value,
            after_value,
            token.color,
            target,
        )

    return 1


def _iter_bfs_with_surface_depth(root: Element) -> Iterable[tuple[Element, int]]:
    queue: deque[tuple[Element, int]] = deque([(root, 0)])
    while queue:
        element, surface_depth = queue.popleft()
        yield element, surface_depth

        category = _element_category(element)
        next_depth = (
            surface_depth + 1
            if category == _CONTAINER_CATEGORY
            else surface_depth
        )
        for child in element.children:
            queue.append((child, next_depth))


def _element_category(element: Element) -> str | None:
    return get_html_element_category(element.tag_name)


def _is_forced_main_surface(element: Element, category: str) -> bool:
    return (
        category == _MAIN_SURFACE_CATEGORY
        or str(element.tag_name or "").strip().lower() in _FORCED_MAIN_SURFACE_TAGS
    )


def _css_data_for(css_property: Property) -> CSSDATA | None:
    return CSSPROPERTIES.get(str(css_property.name or "").strip())


def _property_applies_to_category(css_data: CSSDATA, category: str) -> bool:
    return category in set(css_data.categories or ())


def _skip_color_property(css_property: Property) -> bool:
    property_name = str(css_property.name or "").strip().lower()
    value = str(css_property.value or "")

    if property_name == "background-image":
        return not is_gradient(value)

    if property_name in {
        "border-image",
        "border-image-source",
        "list-style-image",
    }:
        return is_url_image(value) or not _find_color_tokens(value)

    return not _find_color_tokens(value)


def _background_target_tone(
    color: Color,
    category: str,
    surface_depth: int,
) -> int:
    if category == _MAIN_SURFACE_CATEGORY:
        return 0

    if category == _CONTAINER_CATEGORY:
        index = min(
            max(surface_depth, 0),
            len(_CONTAINER_BACKGROUND_TONES) - 1,
        )
        return _CONTAINER_BACKGROUND_TONES[index]

    if category == _INPUT_CATEGORY:
        return _INPUT_BACKGROUND_TONE

    if category in _CONTENT_CATEGORIES:
        current_tone = _tone(color)
        return (
            _CONTENT_BACKGROUND_TONES[0]
            if current_tone >= _LIGHT_BACKGROUND_TONE
            else _CONTENT_BACKGROUND_TONES[1]
        )

    return 20


def _select_visible_muted_color(
    color_scheme: ColorScheme,
    source_color: Color,
    backgrounds: list[Color],
) -> Color:
    return _select_muted_foreground_color(
        color_scheme,
        source_color,
        backgrounds,
    )


def _select_muted_foreground_color(
    color_scheme: ColorScheme,
    source_color: Color,
    backgrounds: list[Color],
) -> Color:
    candidate_tones = (
        _MUTED_FOREGROUND_DARK_BG_TONES
        if not _has_light_background(backgrounds)
        else _MUTED_FOREGROUND_LIGHT_BG_TONES
    )
    candidates = [
        _select_tonal_color(
            color_scheme,
            source_color,
            tone,
            force_neutral=_is_achromatic(source_color),
        )
        for tone in candidate_tones
    ]

    for candidate in candidates:
        if _min_contrast(candidate, backgrounds) >= _MUTED_FOREGROUND_MIN_CONTRAST:
            return candidate

    return max(
        candidates,
        key=lambda candidate: _min_contrast(candidate, backgrounds),
    )


def _select_contrast_color(
    color_scheme: ColorScheme,
    source_color: Color,
    backgrounds: list[Color],
    required_ratio: float,
    *,
    prefer_light: bool,
) -> Color:
    candidate_tones = (
        _LIGHT_FOREGROUND_TONES
        if prefer_light
        else _DARK_FOREGROUND_TONES
    )

    for tone in candidate_tones:
        candidate = _select_tonal_color(
            color_scheme,
            source_color,
            tone,
            force_neutral=_is_achromatic(source_color),
        )
        candidate = _make_opaque(candidate)
        if _min_contrast(candidate, backgrounds) >= required_ratio:
            return candidate

    for tone in candidate_tones:
        candidate = _select_tonal_color(
            color_scheme,
            source_color,
            tone,
            force_neutral=True,
        )
        candidate = _make_opaque(candidate)
        if _min_contrast(candidate, backgrounds) >= required_ratio:
            return candidate

    fallback = Color("white") if prefer_light else Color("black")
    return _make_opaque(fallback)


def _select_tonal_color(
    color_scheme: ColorScheme,
    source_color: Color,
    target_tone: int,
    *,
    force_neutral: bool = False,
) -> Color:
    palette = (
        color_scheme.get_palette(_NEUTRAL_PALETTE_NAME)
        if force_neutral
        else _closest_palette(color_scheme, source_color)
    )

    if palette is None:
        return _copy_alpha(
            source_color,
            _set_hct_tone(source_color, target_tone),
        )

    tone = min(
        palette.tones,
        key=lambda palette_tone: abs(palette_tone.value - target_tone),
    )
    return _copy_alpha(source_color, tone.color)


def _closest_palette(
    color_scheme: ColorScheme,
    source_color: Color,
) -> Palette | None:
    if _is_achromatic(source_color):
        return color_scheme.get_palette(_NEUTRAL_PALETTE_NAME)

    closest_color = color_scheme.find_closest(source_color, "palettes")
    if closest_color is None:
        return None

    palette, _tone_data = color_scheme.resolve_color_location(closest_color)
    return palette


def _set_hct_tone(color: Color, target_tone: int) -> Color:
    return (
        color
        .convert("hct")
        .clone()
        .set("tone", int(target_tone))
        .fit("srgb", method="raytrace", pspace="hct")
        .convert("srgb")
    )


def _copy_alpha(source: Color, target: Color) -> Color:
    alpha = float(source.alpha(nans=False))
    return (
        target
        .clone()
        .convert("srgb")
        .set("alpha", alpha)
    )


def _make_opaque(color: Color) -> Color:
    return (
        color
        .clone()
        .convert("srgb")
        .set("alpha", 1.0)
    )


def _is_achromatic(color: Color) -> bool:
    try:
        return bool(color.is_achromatic())
    except Exception:
        return False


def _required_contrast_ratio(
    page_builder: PageBuilder,
    element: Element,
    category: str,
    property_name: str,
) -> float:
    if category != "typography" or property_name != "color":
        return _NON_TEXT_CONTRAST_RATIO

    try:
        background_data = page_builder.get_background_colors(element.node_id)
    except (RuntimeError, TypeError, ValueError):
        return _TEXT_CONTRAST_RATIO

    font_size = _css_number(background_data.get("font_size"))
    font_weight = _css_font_weight(background_data.get("font_weight"))
    return (
        _LARGE_TEXT_CONTRAST_RATIO
        if font_size >= 18 or (font_size >= 14 and font_weight >= 700)
        else _TEXT_CONTRAST_RATIO
    )


def _background_colors_for(
    page_builder: PageBuilder,
    element: Element,
) -> list[Color]:
    try:
        background_data = page_builder.get_background_colors(element.node_id)
    except (RuntimeError, TypeError, ValueError):
        return [Color("black")]

    raw_backgrounds = background_data.get("background_colors") or []
    colors: list[Color] = []
    for raw_color in raw_backgrounds:
        try:
            color = Color(raw_color)
        except Exception:
            continue
        if color.alpha(nans=False) > 0:
            colors.append(color)

    return colors or [Color("black")]


def _has_light_background(backgrounds: list[Color]) -> bool:
    if not backgrounds:
        return False
    return max(_tone(color) for color in backgrounds) >= _LIGHT_BACKGROUND_TONE


def _min_contrast(foreground: Color, backgrounds: list[Color]) -> float:
    if not backgrounds:
        return foreground.contrast(Color("black"))
    return min(foreground.contrast(background) for background in backgrounds)


def _tone(color: Color) -> float:
    try:
        return float(color.convert("hct")["t"])
    except Exception:
        return 0.0


def _find_color_tokens(value: str) -> list[_ColorToken]:
    if not isinstance(value, str) or not value:
        return []

    found_colors: list[_ColorToken] = []
    start = 0

    while start < len(value):
        match = Color.match(
            value,
            start=start,
            fullmatch=False,
        )

        if match is None:
            start += 1
            continue

        color = match.color
        if color.alpha(nans=False) > 0:
            found_colors.append(
                _ColorToken(
                    text=value[match.start:match.end],
                    color=color,
                )
            )

        start = match.end if match.end > start else start + 1

    return found_colors


def _first_color(value: str) -> Color | None:
    tokens = _find_color_tokens(value)
    return tokens[0].color if tokens else None


def _transform_property_value(
    property_value: str,
    old_values: list[_ColorToken],
    new_values: list[Color],
) -> str:
    return replace_property_values(
        property_value,
        [token.text for token in old_values],
        [_serialize_color(color) for color in new_values],
    )


def _serialize_color(color: Color) -> str:
    srgb = color.convert("srgb").fit("srgb")
    alpha = float(srgb.alpha(nans=False))
    return srgb.to_string(
        comma=True,
        alpha=alpha < _OPAQUE_ALPHA,
    )


def _same_color(left: Color, right: Color) -> bool:
    return (
        left
        .convert("srgb")
        .normalize(nans=False)
        .to_string(comma=True, alpha=True)
        ==
        right
        .convert("srgb")
        .normalize(nans=False)
        .to_string(comma=True, alpha=True)
    )


def _is_border_property(property_name: str) -> bool:
    normalized = str(property_name or "").strip().lower()
    return (
        normalized.startswith("border")
        or normalized.startswith("outline")
        or normalized.startswith("column-rule")
    )


def _is_shadow_property(property_name: str) -> bool:
    return str(property_name or "").strip().lower() in {
        "box-shadow",
        "text-shadow",
    }


def _upsert_property(
    element: Element,
    property_name: str,
    value: str,
    *,
    has_color: bool,
) -> None:
    existing_property = element.property(property_name)
    if existing_property is not None:
        existing_property.value = value
        existing_property.has_color = has_color
        return

    element.properties.append(
        Property(
            name=property_name,
            value=value,
            has_color=has_color,
        )
    )


def _record_change(
    summary: Summary,
    before_code: str,
    after_code: str,
    before_color: Color,
    after_color: Color,
) -> None:
    if _same_color(before_color, after_color):
        return

    summary.add_change(
        change_id=len(summary.changes) + 1,
        before_code=before_code,
        after_code=after_code,
        before_color=before_color,
        after_color=after_color,
    )


def _css_number(value: object) -> float:
    normalized = str(value or "").strip().lower()
    if normalized.endswith("px"):
        normalized = normalized[:-2]
    try:
        return float(normalized)
    except ValueError:
        return 0.0


def _css_font_weight(value: object) -> int:
    normalized = str(value or "").strip().lower()
    keyword_weights = {
        "normal": 400,
        "bold": 700,
        "lighter": 300,
        "bolder": 700,
        "initial": 400,
        "inherit": 400,
        "unset": 400,
        "revert": 400,
    }
    if normalized in keyword_weights:
        return keyword_weights[normalized]
    try:
        return int(float(normalized))
    except ValueError:
        return 400
