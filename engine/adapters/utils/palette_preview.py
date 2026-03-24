from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageDraw, ImageFont

from engine.domain.utils.coloraide import contrast_ratio

_CANVAS_BACKGROUND = "#050608"
_ROW_BACKGROUND = "#101318"
_ROW_OUTLINE = "#262b36"
_TITLE_COLOR = "#f8fafc"
_META_COLOR = "#a5adb8"
_PADDING = 28
_ROW_GAP = 18
_ROW_RADIUS = 18
_ROW_PADDING_X = 18
_ROW_PADDING_Y = 16
_INFO_WIDTH = 180
_INFO_GAP = 20
_SWATCH_WIDTH = 82
_SWATCH_HEIGHT = 82
_SWATCH_GAP = 6
_SWATCH_RADIUS = 8


def _load_font(size: int, *, mono: bool = False) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    font_candidates = (
        ("DejaVuSansMono.ttf", "Consolas.ttf", "Courier New.ttf")
        if mono
        else ("DejaVuSans.ttf", "arial.ttf", "SegoeUI.ttf")
    )
    for font_name in font_candidates:
        try:
            return ImageFont.truetype(font_name, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _palette_rows(palette_analysis: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    core_palettes = dict(palette_analysis.get("core_palettes") or {})
    rows: list[Mapping[str, Any]] = []

    achromatic = core_palettes.get("achromatic_palette")
    if isinstance(achromatic, Mapping):
        rows.append(achromatic)

    for palette in core_palettes.get("chromatic_palettes") or ():
        if isinstance(palette, Mapping):
            rows.append(palette)

    return rows


def _text_color(background_hex: str) -> str:
    white_contrast = contrast_ratio("#ffffff", background_hex)
    dark_contrast = contrast_ratio("#08090b", background_hex)
    return "#ffffff" if white_contrast >= dark_contrast else "#08090b"


def _palette_title(palette: Mapping[str, Any], chromatic_index: int) -> str:
    display_name = str(palette.get("display_name") or "").strip()
    if display_name:
        return display_name
    if palette.get("palette_type") == "achromatic":
        return "Neutral"
    seed_name = str(palette.get("seed_name") or "").strip()
    return seed_name or f"Paleta cromatica {chromatic_index}"


def _palette_meta(palette: Mapping[str, Any]) -> str:
    seed_hex = str(palette.get("seed_hex") or "").upper()
    seed_family_name = str(palette.get("seed_family_name") or "").strip()
    if palette.get("palette_type") == "chromatic" and seed_family_name:
        return f"Seed {seed_hex} | {seed_family_name}" if seed_hex else seed_family_name
    return f"Seed {seed_hex}" if seed_hex else "Seed"


def _row_width(palette: Mapping[str, Any]) -> int:
    tones = tuple(palette.get("tones") or ())
    swatch_count = max(1, len(tones))
    swatch_span = (swatch_count * _SWATCH_WIDTH) + (max(0, swatch_count - 1) * _SWATCH_GAP)
    return (_ROW_PADDING_X * 2) + _INFO_WIDTH + _INFO_GAP + swatch_span


def _row_height() -> int:
    return (_ROW_PADDING_Y * 2) + _SWATCH_HEIGHT


def _draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    *,
    fill: str,
    font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
) -> None:
    draw.text(xy, text, fill=fill, font=font)


def _draw_palette_row(
    draw: ImageDraw.ImageDraw,
    palette: Mapping[str, Any],
    *,
    left: int,
    top: int,
    chromatic_index: int,
    title_font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    meta_font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    tone_font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
    hex_font: ImageFont.ImageFont | ImageFont.FreeTypeFont,
) -> int:
    width = _row_width(palette)
    height = _row_height()
    right = left + width
    bottom = top + height
    tones = tuple(palette.get("tones") or ())

    draw.rounded_rectangle(
        (left, top, right, bottom),
        radius=_ROW_RADIUS,
        fill=_ROW_BACKGROUND,
        outline=_ROW_OUTLINE,
        width=2,
    )

    info_left = left + _ROW_PADDING_X
    info_top = top + _ROW_PADDING_Y
    swatch_left = info_left + _INFO_WIDTH + _INFO_GAP
    swatch_top = top + _ROW_PADDING_Y

    _draw_text(
        draw,
        (info_left, info_top + 4),
        _palette_title(palette, chromatic_index),
        fill=_TITLE_COLOR,
        font=title_font,
    )
    _draw_text(
        draw,
        (info_left, info_top + 36),
        _palette_meta(palette),
        fill=_META_COLOR,
        font=meta_font,
    )

    if not tones:
        return height

    for tone_index, tone_stop in enumerate(tones):
        background_hex = str(tone_stop.get("hex_value") or "#ffffff")
        hex_value = background_hex.upper()
        tone_label = str(tone_stop.get("tone") or "")
        text_fill = _text_color(background_hex)
        block_left = swatch_left + (tone_index * (_SWATCH_WIDTH + _SWATCH_GAP))
        block_top = swatch_top
        block_right = block_left + _SWATCH_WIDTH
        block_bottom = block_top + _SWATCH_HEIGHT

        draw.rounded_rectangle(
            (block_left, block_top, block_right, block_bottom),
            radius=_SWATCH_RADIUS,
            fill=background_hex,
            outline=background_hex,
        )
        _draw_text(
            draw,
            (block_left + 10, block_top + 10),
            tone_label,
            fill=text_fill,
            font=tone_font,
        )
        _draw_text(
            draw,
            (block_left + 10, block_top + 52),
            hex_value,
            fill=text_fill,
            font=hex_font,
        )

    return height


def render_palette_preview(palette_analysis: Mapping[str, Any], output_path: str) -> None:
    rows = _palette_rows(palette_analysis)
    if not rows:
        rows = [
            {
                "palette_id": "palette-empty",
                "palette_type": "achromatic",
                "display_name": "Neutral",
                "seed_hex": "#ffffff",
                "tones": (),
            }
        ]

    title_font = _load_font(24)
    meta_font = _load_font(13)
    tone_font = _load_font(16, mono=True)
    hex_font = _load_font(14, mono=True)

    row_heights = [_row_height() for _ in rows]
    row_widths = [_row_width(palette) for palette in rows]
    canvas_width = (_PADDING * 2) + max(row_widths)
    canvas_height = (_PADDING * 2) + sum(row_heights) + (_ROW_GAP * max(0, len(rows) - 1))

    image = Image.new("RGB", (canvas_width, canvas_height), _CANVAS_BACKGROUND)
    draw = ImageDraw.Draw(image)

    top = _PADDING
    chromatic_index = 0
    for palette in rows:
        if palette.get("palette_type") == "chromatic":
            chromatic_index += 1
        row_height = _draw_palette_row(
            draw,
            palette,
            left=_PADDING,
            top=top,
            chromatic_index=chromatic_index,
            title_font=title_font,
            meta_font=meta_font,
            tone_font=tone_font,
            hex_font=hex_font,
        )
        top += row_height + _ROW_GAP

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
