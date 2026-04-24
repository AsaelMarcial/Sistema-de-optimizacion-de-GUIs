from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable, Mapping, Sequence

from engine.adapters.color_service import color_registry
from engine.domain.data.web_colors import get_web_color
from engine.domain.models.color import Color
from engine.domain.models.palette import (
    ContrastCurveModel,
    CorePalettesModel,
    DynamicSchemeSpecModel,
    MaterialQuantizationAssessment,
    PaletteAnalysisModel,
    PaletteFamilyModel,
    TonalPaletteModel,
)

_MAX_CHROMATIC_PALETTES = 12
_FAMILY_COMPARISON_TONE = 60.0
_FAMILY_HUE_DELTA_THRESHOLD = 12.0
_FAMILY_CHROMA_DELTA_THRESHOLD = 30.0
_FAMILY_NORMALIZED_DELTA_E_THRESHOLD = 10.0
_PIXEL_CONFIRMATION_DELTA_E_THRESHOLD = 6.0


def _hue_distance(left_hue: float, right_hue: float) -> float:
    distance = abs(float(left_hue) - float(right_hue)) % 360.0
    return min(distance, 360.0 - distance)


def _broad_color_family(color_name: str | None, *, palette_type: str) -> str | None:
    if palette_type == "achromatic":
        return "Neutral"
    if not color_name:
        return None
    try:
        return get_web_color(color_name).wikipedia_family
    except Exception:
        return None


def _comparison_signature(value: Any) -> tuple[tuple[int, int, int], tuple[float, float, float]]:
    comparison_color = color_registry.tonal_color(value, _FAMILY_COMPARISON_TONE)
    return (
        color_registry.format_color(comparison_color, "rgb"),
        color_registry.hct_of(comparison_color),
    )  # type: ignore[arg-type]


def _family_from_evidence(evidence: Color) -> PaletteFamilyModel:
    comparison_rgb, comparison_hct = _comparison_signature(evidence.rgb)
    return PaletteFamilyModel(
        palette_type=evidence.family_type,
        seed_color_id=evidence.color_id,
        seed_hex=color_registry.format_color(evidence.rgb, "hex"),
        seed_name=evidence.nearest_web_color,
        seed_family_name=_broad_color_family(
            evidence.nearest_web_color,
            palette_type=evidence.family_type,
        ),
        comparison_rgb=comparison_rgb,
        comparison_hct=comparison_hct,
        semantic_weight=evidence.usage_count,
        pixel_count=evidence.pixel_count,
        foreground_count=evidence.foreground_count,
        background_count=evidence.background_count,
        other_count=evidence.other_count,
        source_color_ids=(evidence.color_id,),
    )


def _family_matches(family: PaletteFamilyModel, evidence: Color) -> bool:
    if family.palette_type != evidence.family_type:
        return False

    if family.palette_type == "chromatic":
        evidence_family_name = _broad_color_family(
            evidence.nearest_web_color,
            palette_type=evidence.family_type,
        )
        if (
            family.seed_family_name
            and evidence_family_name
            and family.seed_family_name != evidence_family_name
        ):
            return False

        comparison_rgb, comparison_hct = _comparison_signature(evidence.rgb)
        normalized_distance = color_registry.delta_e_distance(
            family.comparison_rgb,
            comparison_rgb,
            method="2000",
        )
        hue_delta = _hue_distance(family.comparison_hct[0], comparison_hct[0])
        chroma_delta = abs(float(family.comparison_hct[1]) - float(comparison_hct[1]))

        if (
            hue_delta <= _FAMILY_HUE_DELTA_THRESHOLD
            and chroma_delta <= _FAMILY_CHROMA_DELTA_THRESHOLD
            and normalized_distance <= _FAMILY_NORMALIZED_DELTA_E_THRESHOLD
        ):
            return True

    distance = color_registry.delta_e_distance(family.seed_hex, evidence.rgb, method="2000")
    return distance <= _PIXEL_CONFIRMATION_DELTA_E_THRESHOLD or (
        family.seed_name is not None
        and family.seed_name == evidence.nearest_web_color
        and distance <= 10.0
    )


def _absorb_family(family: PaletteFamilyModel, evidence: Color) -> PaletteFamilyModel:
    source_color_ids = tuple(
        dict.fromkeys((*family.source_color_ids, evidence.color_id)).keys()
    )
    return replace(
        family,
        semantic_weight=family.semantic_weight + evidence.usage_count,
        pixel_count=family.pixel_count + evidence.pixel_count,
        foreground_count=family.foreground_count + evidence.foreground_count,
        background_count=family.background_count + evidence.background_count,
        other_count=family.other_count + evidence.other_count,
        source_color_ids=tuple(source_color_ids),
    )


def _build_families(
    evidences: Sequence[Color],
) -> tuple[PaletteFamilyModel | None, tuple[PaletteFamilyModel, ...]]:
    sorted_evidences = sorted(
        evidences,
        key=lambda evidence: (
            evidence.usage_count,
            evidence.background_count,
            evidence.foreground_count,
            evidence.pixel_count,
        ),
        reverse=True,
    )
    achromatic_families: list[PaletteFamilyModel] = []
    chromatic_families: list[PaletteFamilyModel] = []

    for evidence in sorted_evidences:
        target = achromatic_families if evidence.family_type == "achromatic" else chromatic_families
        match_index = next(
            (index for index, item in enumerate(target) if _family_matches(item, evidence)),
            None,
        )
        if match_index is None:
            target.append(_family_from_evidence(evidence))
            continue
        target[match_index] = _absorb_family(target[match_index], evidence)

    achromatic_families.sort(
        key=lambda family: (family.pixel_count, family.semantic_weight),
        reverse=True,
    )
    chromatic_families.sort(
        key=lambda family: (family.pixel_count, family.semantic_weight),
        reverse=True,
    )
    return (achromatic_families[0] if achromatic_families else None), tuple(chromatic_families)


def _filter_supported_evidences(
    evidences: Sequence[Color],
) -> tuple[Color, ...]:
    return tuple(
        evidence
        for evidence in evidences
        if evidence.usage_count > 0
    )


def _candidate_palettes_for(
    core_palettes: CorePalettesModel,
    evidence: Color,
) -> tuple[TonalPaletteModel, ...]:
    if evidence.family_type == "achromatic":
        return (core_palettes.achromatic_palette,) if core_palettes.achromatic_palette else ()
    if core_palettes.chromatic_palettes:
        return core_palettes.chromatic_palettes
    return (core_palettes.achromatic_palette,) if core_palettes.achromatic_palette else ()


def _map_evidences(
    core_palettes: CorePalettesModel,
    evidences: Sequence[Color],
) -> tuple[Color, ...]:
    mapped_evidences: list[Color] = []
    for evidence in evidences:
        seed_palette = next(
            (
                palette
                for palette in core_palettes
                if palette.seed_color_id is not None and palette.seed_color_id == evidence.color_id
            ),
            None,
        )
        if seed_palette is not None:
            mapped_evidences.append(
                evidence.with_palette_mapping(
                    palette_id=seed_palette.palette_id,
                    tone=int(round(seed_palette.seed_hct[2])),
                    tone_rgb=seed_palette.seed_rgb,
                    tone_distance=0.0,
                )
            )
            continue

        best_palette: TonalPaletteModel | None = None
        best_tone = None
        best_distance: float | None = None

        for palette in _candidate_palettes_for(core_palettes, evidence):
            tone_stop, distance = palette.nearest_tone_to(evidence.rgb)
            if tone_stop is None or distance is None:
                continue
            if best_distance is None or distance < best_distance:
                best_palette = palette
                best_tone = tone_stop
                best_distance = distance

        if best_palette is None or best_tone is None or best_distance is None:
            mapped_evidences.append(evidence)
            continue

        mapped_evidences.append(
            evidence.with_palette_mapping(
                palette_id=best_palette.palette_id,
                tone=best_tone.tone,
                tone_rgb=best_tone.rgb,
                tone_distance=best_distance,
            )
        )
    return tuple(mapped_evidences)


def _build_named_color_breakdown(
    evidences: Sequence[Color],
    *,
    total_pixels: int,
) -> tuple[dict[str, Any], ...]:
    use_pixel_weight = total_pixels > 0
    breakdown: dict[str, dict[str, Any]] = {}
    total_weight = 0

    for evidence in evidences:
        weight = evidence.pixel_count if use_pixel_weight else evidence.usage_count
        if weight <= 0 or not evidence.nearest_web_color:
            continue
        total_weight += weight
        named_color = get_web_color(evidence.nearest_web_color)
        item = breakdown.setdefault(
            evidence.nearest_web_color,
            {
                "name": evidence.nearest_web_color,
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


def _build_dynamic_scheme(
    core_palettes: CorePalettesModel,
    evidences: Sequence[Color],
) -> DynamicSchemeSpecModel:
    achromatic_palette = core_palettes.achromatic_palette
    primary_palette = (
        core_palettes.chromatic_palettes[0]
        if core_palettes.chromatic_palettes
        else achromatic_palette
    )
    return DynamicSchemeSpecModel(
        scheme_id="project-color-analysis",
        source_color_ids=tuple(evidence.color_id for evidence in evidences),
        primary_palette_id=primary_palette.palette_id if primary_palette else None,
        achromatic_palette_id=achromatic_palette.palette_id if achromatic_palette else None,
        chromatic_palette_ids=tuple(
            palette.palette_id for palette in core_palettes.chromatic_palettes
        ),
        contrast_curve=ContrastCurveModel(low=3.0, normal=4.5, medium=7.0, high=11.0),
    )


def build_palette_analysis(
    snapshot_palette: Iterable[Mapping[str, Any] | Color],
    *,
    material_quantization_assessment: MaterialQuantizationAssessment,
    max_chromatic_palettes: int = _MAX_CHROMATIC_PALETTES,
) -> PaletteAnalysisModel:
    semantic_colors = _filter_supported_evidences(
        Color.build_many(snapshot_palette)
    )
    achromatic_family, chromatic_families = _build_families(semantic_colors)
    core_palettes = CorePalettesModel.build(
        achromatic_family=achromatic_family,
        chromatic_families=chromatic_families,
        max_chromatic_palettes=max_chromatic_palettes,
    )
    mapped_evidences = _map_evidences(core_palettes, semantic_colors)
    pixel_count = sum(evidence.pixel_count for evidence in mapped_evidences)
    return PaletteAnalysisModel.build_from_components(
        semantic_colors=mapped_evidences,
        named_color_breakdown=_build_named_color_breakdown(
            mapped_evidences,
            total_pixels=pixel_count,
        ),
        core_palettes=core_palettes,
        dynamic_scheme=_build_dynamic_scheme(core_palettes, mapped_evidences),
        material_quantization_assessment=material_quantization_assessment,
    )
