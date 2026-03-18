from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from typing import Any, Iterable, Mapping, Sequence

from engine.domain.data.web_colors import get_web_color, nearest_web_color
from engine.domain.enums.scope.css_properties import CSS_PROPERTIES_BY_ID, CssColorRole
from engine.domain.models.color import PixelColorRecord, SnapshotColorEvidence
from engine.domain.models.palette import (
    ContrastCurveModel,
    CorePalettesModel,
    DynamicSchemeSpecModel,
    MaterialQuantizationAssessment,
    PaletteAnalysisModel,
    TonalPaletteModel,
)
from engine.domain.models.style import PropertyUsageModel, TagUsageModel
from engine.domain.utils.colors import (
    alpha_value,
    color_to_hex,
    color_to_rgb_tuple,
    delta_e_distance,
    hct_coords,
    parse_color,
    tonal_palette_color,
)

_ACHROMATIC_CHROMA_THRESHOLD = 8.0
_ACHROMATIC_PALETTE_CHROMA = 6.0
_PIXEL_CONFIRMATION_DELTA_E_THRESHOLD = 6.0
_MAX_CHROMATIC_PALETTES = 12
_FAMILY_COMPARISON_TONE = 60.0
_FAMILY_HUE_DELTA_THRESHOLD = 12.0
_FAMILY_CHROMA_DELTA_THRESHOLD = 30.0
_FAMILY_NORMALIZED_DELTA_E_THRESHOLD = 10.0
_WEB_FAMILY_DISPLAY_NAMES = {
    "Colores rojos": "Red",
    "Colores naranjas": "Orange",
    "Colores marrones": "Brown",
    "Colores amarillos": "Yellow",
    "Colores verdes amarillos": "Lime",
    "Colores verdes": "Green",
    "Colores acianos (azul verdes)": "Turquoise",
    "Colores azules": "Blue",
    "Colores violetas y púrpuras": "Violet",
    "Colores rosas": "Fuchsia / Magenta",
    "Colores blancos": "White",
    "Colores grises": "Neutral",
}


@dataclass(slots=True)
class _PaletteFamilyAccumulator:
    palette_type: str
    seed_color_id: str | None
    seed_hex: str
    seed_name: str | None
    seed_family_name: str | None
    comparison_rgb: tuple[int, int, int]
    comparison_hct: tuple[float, float, float]
    semantic_weight: int
    confirmed_pixel_count: int
    foreground_count: int
    background_count: int
    other_count: int
    source_color_ids: list[str]

    def absorb(self, evidence: SnapshotColorEvidence) -> None:
        self.semantic_weight += evidence.usage_count
        self.confirmed_pixel_count += evidence.confirmed_pixel_count
        self.foreground_count += evidence.foreground_count
        self.background_count += evidence.background_count
        self.other_count += evidence.other_count
        if evidence.color_id not in self.source_color_ids:
            self.source_color_ids.append(evidence.color_id)

def _role_bias(
    *,
    foreground_count: int,
    background_count: int,
    other_count: int,
) -> str:
    if background_count > foreground_count and background_count >= other_count:
        return "background"
    if foreground_count > background_count and foreground_count >= other_count:
        return "foreground"
    if other_count > max(background_count, foreground_count):
        return "other"
    return "mixed"


def _family_type_for_hct(hct_chroma: float) -> str:
    return "achromatic" if hct_chroma < _ACHROMATIC_CHROMA_THRESHOLD else "chromatic"


def _specific_palette_name(color_name: str | None) -> str | None:
    if not color_name:
        return None
    try:
        return get_web_color(color_name).display_name
    except Exception:
        return color_name.replace("_", " ").title()


def _family_palette_name(color_name: str | None, *, palette_type: str) -> str:
    if palette_type == "achromatic":
        return "Neutral"
    if not color_name:
        return "Chromatic"
    try:
        return _WEB_FAMILY_DISPLAY_NAMES.get(
            get_web_color(color_name).wikipedia_family,
            get_web_color(color_name).display_name,
        )
    except Exception:
        return color_name.replace("_", " ").title()


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
    comparison_color = tonal_palette_color(value, _FAMILY_COMPARISON_TONE)
    return color_to_rgb_tuple(comparison_color), hct_coords(comparison_color)  # type: ignore[arg-type]


def _hue_distance(left_hue: float, right_hue: float) -> float:
    distance = abs(float(left_hue) - float(right_hue)) % 360.0
    return min(distance, 360.0 - distance)


def _build_property_usage_models(
    usages_by_property: Mapping[str, Mapping[str, int]],
) -> tuple[PropertyUsageModel, ...]:
    models: list[PropertyUsageModel] = []
    for property_name, tag_counts in sorted(usages_by_property.items()):
        tag_models = tuple(
            TagUsageModel(tag=tag_name, count=count)
            for tag_name, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
        )
        models.append(
            PropertyUsageModel(
                property_name=property_name,
                total_count=sum(item.count for item in tag_models),
                tags=tag_models,
            )
        )
    return tuple(models)


def _build_snapshot_color_evidence(entry: Mapping[str, Any]) -> SnapshotColorEvidence | None:
    value = str(entry.get("value") or "").strip()
    if not value:
        return None

    hct = hct_coords(value)
    rgb = color_to_rgb_tuple(value)
    match = nearest_web_color(rgb)

    foreground_count = 0
    background_count = 0
    other_count = 0
    foreground_usages: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    background_usages: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    other_usages: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for usage in entry.get("usage", ()) or ():
        property_name = str(usage.get("property") or "")
        tag_name = str(usage.get("tag") or "")
        count = int(usage.get("count") or 0)
        property_spec = CSS_PROPERTIES_BY_ID.get(property_name)
        if property_spec and property_spec.color_role == CssColorRole.BACKGROUND:
            background_count += count
            background_usages[property_name][tag_name] += count
        elif property_spec and property_spec.color_role == CssColorRole.FOREGROUND:
            foreground_count += count
            foreground_usages[property_name][tag_name] += count
        else:
            other_count += count
            other_usages[property_name][tag_name] += count

    return SnapshotColorEvidence(
        color_id=str(entry.get("color_id") or ""),
        rgb=rgb,
        alpha=alpha_value(value),
        hct=hct,  # type: ignore[arg-type]
        family_type=_family_type_for_hct(hct[1]),
        usage_count=int(entry.get("usage_count") or 0),
        foreground_count=foreground_count,
        background_count=background_count,
        other_count=other_count,
        foreground_color_usages=_build_property_usage_models(foreground_usages),
        background_color_usages=_build_property_usage_models(background_usages),
        other_usages=_build_property_usage_models(other_usages),
        nearest_web_color=match.color_name,
        nearest_web_color_distance=round(match.distance, 4),
    )


def _normalize_pixel_records(
    pixel_color_frequencies: Sequence[Mapping[str, Any]] | None,
) -> tuple[PixelColorRecord, ...]:
    if not pixel_color_frequencies:
        return ()
    return tuple(PixelColorRecord.from_mapping(item) for item in pixel_color_frequencies)


def _confirm_snapshot_colors(
    evidences: Sequence[SnapshotColorEvidence],
    pixel_records: Sequence[PixelColorRecord],
) -> tuple[tuple[SnapshotColorEvidence, ...], int, int]:
    if not evidences:
        residual_pixels = sum(item.count for item in pixel_records)
        return (), 0, residual_pixels

    evidence_colors = {evidence.color_id: parse_color(evidence.rgb) for evidence in evidences}
    confirmed_counts = {evidence.color_id: 0 for evidence in evidences}
    residual_pixel_count = 0
    residual_distinct_colors = 0

    for pixel_record in pixel_records:
        pixel_color = parse_color(pixel_record.color)
        best_match = min(
            evidences,
            key=lambda evidence: delta_e_distance(
                pixel_color,
                evidence_colors[evidence.color_id],
                method="2000",
            ),
        )
        distance = delta_e_distance(pixel_color, evidence_colors[best_match.color_id], method="2000")
        if distance <= _PIXEL_CONFIRMATION_DELTA_E_THRESHOLD:
            confirmed_counts[best_match.color_id] += pixel_record.count
        else:
            residual_pixel_count += pixel_record.count
            residual_distinct_colors += 1

    confirmed_evidences: list[SnapshotColorEvidence] = []
    for evidence in evidences:
        confirmed_pixel_count = confirmed_counts[evidence.color_id]
        confirmed_evidences.append(
            replace(
                evidence,
                confirmed_pixel_count=confirmed_pixel_count,
                confirmation_status="confirmed" if confirmed_pixel_count > 0 else "semantic_only",
            )
        )

    return tuple(confirmed_evidences), residual_distinct_colors, residual_pixel_count


def _should_merge_family(
    family: _PaletteFamilyAccumulator,
    evidence: SnapshotColorEvidence,
) -> bool:
    if family.palette_type != evidence.family_type:
        return False

    if family.palette_type == "chromatic":
        evidence_family_name = _broad_color_family(
            evidence.nearest_web_color,
            palette_type=evidence.family_type,
        )
        if family.seed_family_name and evidence_family_name and family.seed_family_name != evidence_family_name:
            return False

        comparison_rgb, comparison_hct = _comparison_signature(evidence.rgb)
        normalized_distance = delta_e_distance(family.comparison_rgb, comparison_rgb, method="2000")
        hue_delta = _hue_distance(family.comparison_hct[0], comparison_hct[0])
        chroma_delta = abs(float(family.comparison_hct[1]) - float(comparison_hct[1]))

        if (
            hue_delta <= _FAMILY_HUE_DELTA_THRESHOLD
            and chroma_delta <= _FAMILY_CHROMA_DELTA_THRESHOLD
            and normalized_distance <= _FAMILY_NORMALIZED_DELTA_E_THRESHOLD
        ):
            return True

    distance = delta_e_distance(family.seed_hex, evidence.rgb, method="2000")
    if distance <= _PIXEL_CONFIRMATION_DELTA_E_THRESHOLD:
        return True
    return family.seed_name is not None and family.seed_name == evidence.nearest_web_color and distance <= 10.0


def _build_palette_families(
    evidences: Sequence[SnapshotColorEvidence],
) -> tuple[_PaletteFamilyAccumulator | None, tuple[_PaletteFamilyAccumulator, ...]]:
    sorted_evidences = sorted(
        evidences,
        key=lambda evidence: (
            evidence.confirmed_pixel_count,
            evidence.usage_count,
            evidence.background_count,
            evidence.foreground_count,
        ),
        reverse=True,
    )

    achromatic_families: list[_PaletteFamilyAccumulator] = []
    chromatic_families: list[_PaletteFamilyAccumulator] = []

    for evidence in sorted_evidences:
        target = achromatic_families if evidence.family_type == "achromatic" else chromatic_families
        merged = False
        for family in target:
            if _should_merge_family(family, evidence):
                family.absorb(evidence)
                merged = True
                break
        if merged:
            continue
        comparison_rgb, comparison_hct = _comparison_signature(evidence.rgb)
        target.append(
            _PaletteFamilyAccumulator(
                palette_type=evidence.family_type,
                seed_color_id=evidence.color_id,
                seed_hex=color_to_hex(evidence.rgb),
                seed_name=evidence.nearest_web_color,
                seed_family_name=_broad_color_family(
                    evidence.nearest_web_color,
                    palette_type=evidence.family_type,
                ),
                comparison_rgb=comparison_rgb,
                comparison_hct=comparison_hct,
                semantic_weight=evidence.usage_count,
                confirmed_pixel_count=evidence.confirmed_pixel_count,
                foreground_count=evidence.foreground_count,
                background_count=evidence.background_count,
                other_count=evidence.other_count,
                source_color_ids=[evidence.color_id],
            )
        )

    achromatic_families.sort(
        key=lambda family: (family.confirmed_pixel_count, family.semantic_weight),
        reverse=True,
    )
    chromatic_families.sort(
        key=lambda family: (family.confirmed_pixel_count, family.semantic_weight),
        reverse=True,
    )
    return (achromatic_families[0] if achromatic_families else None), tuple(chromatic_families)


def _fallback_achromatic_palette() -> TonalPaletteModel:
    return TonalPaletteModel.from_seed(
        palette_id="palette-achromatic-1",
        palette_type="achromatic",
        seed_hex="#ffffff",
        role_bias="background",
        semantic_weight=0,
        confirmed_pixel_count=0,
        seed_name="white",
        source_color_ids=(),
        chroma_override=_ACHROMATIC_PALETTE_CHROMA,
    )


def _palette_candidates_for_evidence(
    evidence: SnapshotColorEvidence,
    core_palettes: CorePalettesModel,
) -> tuple[TonalPaletteModel, ...]:
    if evidence.family_type == "achromatic":
        return (core_palettes.achromatic_palette,) if core_palettes.achromatic_palette else ()

    if core_palettes.chromatic_palettes:
        return core_palettes.chromatic_palettes

    return (core_palettes.achromatic_palette,) if core_palettes.achromatic_palette else ()


def _map_evidences_to_palettes(
    evidences: Sequence[SnapshotColorEvidence],
    core_palettes: CorePalettesModel,
) -> tuple[SnapshotColorEvidence, ...]:
    mapped_evidences: list[SnapshotColorEvidence] = []

    for evidence in evidences:
        candidate_palettes = _palette_candidates_for_evidence(evidence, core_palettes)
        best_palette: TonalPaletteModel | None = None
        best_tone = None
        best_distance: float | None = None

        for palette in candidate_palettes:
            for tone_stop in palette.tones:
                distance = delta_e_distance(
                    evidence.rgb,
                    tone_stop.rgb,
                    method="2000",
                )
                if best_distance is None or distance < best_distance:
                    best_palette = palette
                    best_tone = tone_stop
                    best_distance = distance

        if best_palette is None or best_tone is None or best_distance is None:
            mapped_evidences.append(evidence)
            continue

        mapped_evidences.append(
            replace(
                evidence,
                mapped_palette_id=best_palette.palette_id,
                mapped_tone=best_tone.tone,
                mapped_tone_rgb=best_tone.rgb,
                mapped_tone_distance=round(best_distance, 4),
            )
        )

    return tuple(mapped_evidences)


def _family_to_palette(
    family: _PaletteFamilyAccumulator,
    *,
    palette_index: int,
) -> TonalPaletteModel:
    role_bias = _role_bias(
        foreground_count=family.foreground_count,
        background_count=family.background_count,
        other_count=family.other_count,
    )
    return TonalPaletteModel.from_seed(
        palette_id=f"palette-{family.palette_type}-{palette_index}",
        palette_type=family.palette_type,
        seed_hex=family.seed_hex,
        role_bias=role_bias,
        semantic_weight=family.semantic_weight,
        confirmed_pixel_count=family.confirmed_pixel_count,
        seed_name=family.seed_name,
        seed_color_id=family.seed_color_id,
        source_color_ids=tuple(family.source_color_ids),
        chroma_override=(
            _ACHROMATIC_PALETTE_CHROMA if family.palette_type == "achromatic" else None
        ),
    )


def _annotate_palette_names(core_palettes: CorePalettesModel) -> CorePalettesModel:
    achromatic_palette = core_palettes.achromatic_palette
    if achromatic_palette is not None:
        achromatic_palette = replace(
            achromatic_palette,
            display_name="Base achromatica",
            seed_display_name=_specific_palette_name(achromatic_palette.seed_name),
            seed_family_name="Neutral",
        )

    family_names = [
        _family_palette_name(palette.seed_name, palette_type=palette.palette_type)
        for palette in core_palettes.chromatic_palettes
    ]
    family_counts = Counter(family_names)

    named_chromatic_palettes: list[TonalPaletteModel] = []
    for palette, family_name in zip(core_palettes.chromatic_palettes, family_names):
        specific_name = _specific_palette_name(palette.seed_name)
        display_name = family_name if family_counts[family_name] <= 1 else (specific_name or family_name)
        named_chromatic_palettes.append(
            replace(
                palette,
                display_name=display_name,
                seed_display_name=specific_name,
                seed_family_name=family_name,
            )
        )

    return CorePalettesModel(
        achromatic_palette=achromatic_palette,
        chromatic_palettes=tuple(named_chromatic_palettes),
        max_chromatic_palettes=core_palettes.max_chromatic_palettes,
    )


def _build_named_color_breakdown(
    evidences: Sequence[SnapshotColorEvidence],
    *,
    total_confirmed_pixels: int,
) -> tuple[dict[str, Any], ...]:
    use_confirmed_pixels = total_confirmed_pixels > 0
    breakdown: dict[str, dict[str, Any]] = {}
    total_weight = 0

    for evidence in evidences:
        weight = evidence.confirmed_pixel_count if use_confirmed_pixels else evidence.usage_count
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

    normalized_items = []
    for item in breakdown.values():
        normalized_items.append(
            {
                **item,
                "percentage": round((item["count"] / total_weight) * 100, 4),
            }
        )

    normalized_items.sort(key=lambda item: (item["count"], item["name"]), reverse=True)
    return tuple(normalized_items)


def build_palette_analysis(
    snapshot_palette: Iterable[Mapping[str, Any]],
    pixel_color_frequencies: Sequence[Mapping[str, Any]] | None,
    *,
    material_quantization_assessment: MaterialQuantizationAssessment,
    max_chromatic_palettes: int = _MAX_CHROMATIC_PALETTES,
) -> PaletteAnalysisModel:
    semantic_colors = tuple(
        evidence
        for evidence in (
            _build_snapshot_color_evidence(entry)
            for entry in snapshot_palette
        )
        if evidence is not None
    )
    pixel_records = _normalize_pixel_records(pixel_color_frequencies)
    confirmed_evidences, residual_distinct_colors, residual_pixel_count = _confirm_snapshot_colors(
        semantic_colors,
        pixel_records,
    )
    confirmed_pixel_count = sum(evidence.confirmed_pixel_count for evidence in confirmed_evidences)
    achromatic_family, chromatic_families = _build_palette_families(confirmed_evidences)

    achromatic_palette = (
        _family_to_palette(achromatic_family, palette_index=1)
        if achromatic_family is not None
        else _fallback_achromatic_palette()
    )
    chromatic_palettes = tuple(
        _family_to_palette(family, palette_index=index)
        for index, family in enumerate(chromatic_families[:max_chromatic_palettes], start=1)
    )
    core_palettes = CorePalettesModel(
        achromatic_palette=achromatic_palette,
        chromatic_palettes=chromatic_palettes,
        max_chromatic_palettes=max_chromatic_palettes,
    )
    core_palettes = _annotate_palette_names(core_palettes)
    mapped_evidences = _map_evidences_to_palettes(confirmed_evidences, core_palettes)

    dynamic_scheme = DynamicSchemeSpecModel(
        scheme_id="project-color-analysis",
        source_color_ids=tuple(evidence.color_id for evidence in mapped_evidences),
        primary_palette_id=(
            chromatic_palettes[0].palette_id if chromatic_palettes else achromatic_palette.palette_id
        ),
        achromatic_palette_id=achromatic_palette.palette_id,
        chromatic_palette_ids=tuple(palette.palette_id for palette in chromatic_palettes),
        contrast_curve=ContrastCurveModel(low=3.0, normal=4.5, medium=7.0, high=11.0),
    )

    return PaletteAnalysisModel(
        semantic_colors=mapped_evidences,
        named_color_breakdown=_build_named_color_breakdown(
            mapped_evidences,
            total_confirmed_pixels=confirmed_pixel_count,
        ),
        core_palettes=core_palettes,
        dynamic_scheme=dynamic_scheme,
        material_quantization_assessment=material_quantization_assessment,
        confirmed_pixel_count=confirmed_pixel_count,
        residual_pixel_count=residual_pixel_count,
        residual_distinct_colors=residual_distinct_colors,
    )
