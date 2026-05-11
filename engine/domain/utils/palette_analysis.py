from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from engine.adapters.color_service import color_registry
from engine.domain.data.web_colors import get_web_color
from engine.domain.enums.types.color import ColorFamilyType, PaletteRoleBias
from engine.domain.models.color import Color
from engine.domain.models.color_scheme import ColorSchemeModel, TonalPaletteModel
from engine.domain.models.palette import ColorSchemeArtifactModel

_FAMILY_COMPARISON_TONE = 60.0
_FAMILY_HUE_DELTA_THRESHOLD = 12.0
_FAMILY_CHROMA_DELTA_THRESHOLD = 30.0
_FAMILY_NORMALIZED_DELTA_E_THRESHOLD = 10.0
_FAMILY_FALLBACK_MATCH_DELTA_E = 6.0


def _hue_distance(left_hue: float, right_hue: float) -> float:
    distance = abs(float(left_hue) - float(right_hue)) % 360.0
    return min(distance, 360.0 - distance)


def _broad_color_family(color_name: str | None, *, palette_type: ColorFamilyType | str) -> str | None:
    if palette_type == ColorFamilyType.ACHROMATIC or str(palette_type) == ColorFamilyType.ACHROMATIC.value:
        return "Neutral"
    if not color_name:
        return None
    try:
        return get_web_color(color_name).wikipedia_family
    except Exception:
        return None


def _role_bias(seed: Mapping[str, Any]) -> PaletteRoleBias:
    background_count = int(seed.get("background_count") or 0)
    foreground_count = int(seed.get("foreground_count") or 0)
    other_count = int(seed.get("other_count") or 0)
    if background_count > foreground_count and background_count >= other_count:
        return PaletteRoleBias.BACKGROUND
    if foreground_count > background_count and foreground_count >= other_count:
        return PaletteRoleBias.FOREGROUND
    if other_count > max(background_count, foreground_count):
        return PaletteRoleBias.OTHER
    return PaletteRoleBias.MIXED


def _comparison_signature(value: Any) -> tuple[tuple[int, int, int], tuple[float, float, float]]:
    comparison_color = color_registry.tonal_color(value, _FAMILY_COMPARISON_TONE)
    return (
        color_registry.format_color(comparison_color, "rgb"),
        color_registry.hct_of(comparison_color),
    )  # type: ignore[arg-type]


def _seed_from_color(evidence: Color) -> dict[str, Any]:
    comparison_rgb, comparison_hct = _comparison_signature(evidence.rgb)
    seed = {
        "palette_type": evidence.family_type,
        "seed_color_id": evidence.color_id,
        "seed_hex": color_registry.format_color(evidence.rgb, "hex"),
        "seed_name": evidence.nearest_web_color,
        "seed_family_name": _broad_color_family(
            evidence.nearest_web_color,
            palette_type=evidence.family_type,
        ),
        "comparison_rgb": comparison_rgb,
        "comparison_hct": comparison_hct,
        "semantic_weight": evidence.usage_count,
        "pixel_count": evidence.pixel_count,
        "foreground_count": evidence.foreground_count,
        "background_count": evidence.background_count,
        "other_count": evidence.other_count,
    }
    seed["role_bias"] = _role_bias(seed)
    return seed


def _seed_matches(seed: Mapping[str, Any], evidence: Color) -> bool:
    palette_type = seed.get("palette_type")
    if str(palette_type) != evidence.family_type.value:
        return False

    if evidence.family_type == ColorFamilyType.CHROMATIC:
        evidence_family_name = _broad_color_family(
            evidence.nearest_web_color,
            palette_type=evidence.family_type,
        )
        seed_family_name = seed.get("seed_family_name")
        if seed_family_name and evidence_family_name and seed_family_name != evidence_family_name:
            return False

        comparison_rgb, comparison_hct = _comparison_signature(evidence.rgb)
        seed_rgb = tuple(int(channel) for channel in seed["comparison_rgb"])
        seed_hct = tuple(float(channel) for channel in seed["comparison_hct"])
        normalized_distance = color_registry.delta_e_distance(
            seed_rgb,
            comparison_rgb,
            method="2000",
        )
        hue_delta = _hue_distance(seed_hct[0], comparison_hct[0])
        chroma_delta = abs(seed_hct[1] - float(comparison_hct[1]))

        if (
            hue_delta <= _FAMILY_HUE_DELTA_THRESHOLD
            and chroma_delta <= _FAMILY_CHROMA_DELTA_THRESHOLD
            and normalized_distance <= _FAMILY_NORMALIZED_DELTA_E_THRESHOLD
        ):
            return True

    distance = color_registry.delta_e_distance(seed["seed_hex"], evidence.rgb, method="2000")
    return distance <= _FAMILY_FALLBACK_MATCH_DELTA_E or (
        seed.get("seed_name") is not None
        and seed.get("seed_name") == evidence.nearest_web_color
        and distance <= 10.0
    )


def _absorb_seed(seed: Mapping[str, Any], evidence: Color) -> dict[str, Any]:
    updated = dict(seed)
    updated["semantic_weight"] = int(updated.get("semantic_weight") or 0) + evidence.usage_count
    updated["pixel_count"] = int(updated.get("pixel_count") or 0) + evidence.pixel_count
    updated["foreground_count"] = int(updated.get("foreground_count") or 0) + evidence.foreground_count
    updated["background_count"] = int(updated.get("background_count") or 0) + evidence.background_count
    updated["other_count"] = int(updated.get("other_count") or 0) + evidence.other_count
    updated["role_bias"] = _role_bias(updated)
    return updated


def filter_supported_colors(
    colors: Iterable[Mapping[str, Any] | Color],
) -> tuple[Color, ...]:
    return tuple(
        color
        for color in Color.build_many(colors)
        if color.usage_count > 0
    )


def build_palette_seed_specs(
    colors: Sequence[Color],
) -> tuple[Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]:
    sorted_colors = sorted(
        colors,
        key=lambda color: (
            color.usage_count,
            color.background_count,
            color.foreground_count,
            color.pixel_count,
        ),
        reverse=True,
    )
    achromatic_seeds: list[dict[str, Any]] = []
    chromatic_seeds: list[dict[str, Any]] = []

    for color in sorted_colors:
        target = achromatic_seeds if color.family_type == ColorFamilyType.ACHROMATIC else chromatic_seeds
        match_index = next(
            (index for index, seed in enumerate(target) if _seed_matches(seed, color)),
            None,
        )
        if match_index is None:
            target.append(_seed_from_color(color))
            continue
        target[match_index] = _absorb_seed(target[match_index], color)

    achromatic_seeds.sort(
        key=lambda seed: (int(seed.get("pixel_count") or 0), int(seed.get("semantic_weight") or 0)),
        reverse=True,
    )
    chromatic_seeds.sort(
        key=lambda seed: (int(seed.get("pixel_count") or 0), int(seed.get("semantic_weight") or 0)),
        reverse=True,
    )
    return (achromatic_seeds[0] if achromatic_seeds else None), tuple(chromatic_seeds)


def _candidate_palettes_for(
    scheme: ColorSchemeModel,
    color: Color,
) -> tuple[TonalPaletteModel, ...]:
    if color.family_type == ColorFamilyType.ACHROMATIC:
        return (scheme.achromatic_palette,) if scheme.achromatic_palette else ()
    if scheme.chromatic_palettes:
        return scheme.chromatic_palettes
    return (scheme.achromatic_palette,) if scheme.achromatic_palette else ()


def map_colors_to_scheme(
    scheme: ColorSchemeModel,
    colors: Sequence[Color],
) -> tuple[Color, ...]:
    mapped_colors: list[Color] = []
    for color in colors:
        seed_palette = next(
            (
                palette
                for palette in scheme
                if palette.seed_color_id is not None and palette.seed_color_id == color.color_id
            ),
            None,
        )
        if seed_palette is not None:
            mapped_colors.append(
                color.with_palette_mapping(
                    palette_id=seed_palette.palette_id,
                    tone=seed_palette.seed_tone(),
                    tone_rgb=seed_palette.seed_rgb(),
                    tone_distance=0.0,
                )
            )
            continue

        best_palette: TonalPaletteModel | None = None
        best_tone = None
        best_distance: float | None = None

        for palette in _candidate_palettes_for(scheme, color):
            tone_stop, distance = palette.nearest_tone_to(color.rgb)
            if tone_stop is None or distance is None:
                continue
            if best_distance is None or distance < best_distance:
                best_palette = palette
                best_tone = tone_stop
                best_distance = distance

        if best_palette is None or best_tone is None or best_distance is None:
            mapped_colors.append(color)
            continue

        mapped_colors.append(
            color.with_palette_mapping(
                palette_id=best_palette.palette_id,
                tone=best_tone.tone,
                tone_rgb=best_tone.rgb,
                tone_distance=best_distance,
            )
        )
    return tuple(mapped_colors)


def build_named_color_breakdown(
    colors: Sequence[Color],
    *,
    total_pixels: int,
) -> tuple[dict[str, Any], ...]:
    use_pixel_weight = total_pixels > 0
    breakdown: dict[str, dict[str, Any]] = {}
    total_weight = 0

    for color in colors:
        weight = color.pixel_count if use_pixel_weight else color.usage_count
        if weight <= 0 or not color.nearest_web_color:
            continue
        total_weight += weight
        named_color = get_web_color(color.nearest_web_color)
        item = breakdown.setdefault(
            color.nearest_web_color,
            {
                "name": color.nearest_web_color,
                "display_name": named_color.display_name,
                "family": named_color.wikipedia_family,
                "hex_value": named_color.hex_value,
                "count": 0,
                "percentage": 0.0,
            },
        )
        item["count"] += weight

    if total_weight == 0:
        return ()

    normalized_items = [
        {
            **item,
            "percentage": round((item["count"] / total_weight) * 100, 4),
        }
        for item in breakdown.values()
    ]
    normalized_items.sort(key=lambda item: (item["count"], item["name"]), reverse=True)
    return tuple(normalized_items)


def build_palette_analysis(
    *,
    snapshot_palette: Iterable[Mapping[str, Any] | Color],
    material_quantization_assessment: Any,
    max_chromatic_palettes: int = 12,
) -> ColorSchemeArtifactModel:
    semantic_colors = filter_supported_colors(snapshot_palette)
    achromatic_seed, chromatic_seeds = build_palette_seed_specs(semantic_colors)
    core_palettes = ColorSchemeModel.build(
        achromatic_seed=achromatic_seed,
        chromatic_seeds=chromatic_seeds[:max_chromatic_palettes],
    )
    mapped_colors = map_colors_to_scheme(core_palettes, semantic_colors)
    named_color_breakdown = build_named_color_breakdown(
        mapped_colors,
        total_pixels=sum(color.pixel_count for color in mapped_colors),
    )
    return ColorSchemeArtifactModel.build_from_components(
        semantic_colors=mapped_colors,
        named_color_breakdown=named_color_breakdown,
        core_palettes=core_palettes,
        dynamic_scheme={},
        material_quantization_assessment=material_quantization_assessment,
    )
