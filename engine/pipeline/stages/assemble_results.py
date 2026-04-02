from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from engine.adapters.file_system.file_handler import create_output_bundle
from engine.adapters.utils.io import save_json
from engine.domain.data.web_colors import nearest_web_color
from engine.domain.models.color import build_inventory_from_scheme_colors
from engine.domain.models.environmental_assessment.assessment import (
    EnvironmentalAssessmentModel,
    EnvironmentalSavingsModel,
)
from engine.domain.models.color import DisplayPixelFrequenciesModel
from engine.domain.models.palette import CorePalettesModel
from engine.domain.models.session import Session
from engine.domain.models.token import TokenInventoryModel
from engine.adapters.color_service import color_registry
from engine.domain.utils.formatters import color_frequency_to_statistics
from engine.pipeline.context import PipelineContext, RecommendationsPayload
from engine.pipeline.stage_contract import StageContract, context_value

_TONE_STOPS = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 100)
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


def _session_ready_for_results(session: Session) -> bool:
    return (
        bool(session.output_dir.strip())
        and bool(session.artifacts_dir.strip())
        and bool(session.results_json_path.strip())
        and bool(session.bundle_name.strip())
        and bool(session.download_path.strip())
    )

CONTRACT = StageContract(
    name="assemble_results",
    requires=(
        context_value("environmental.assessment.before", EnvironmentalAssessmentModel),
        context_value("environmental.assessment.after", EnvironmentalAssessmentModel),
        context_value("environmental.assessment.savings", EnvironmentalSavingsModel),
        context_value("scheme.colors", tuple),
        context_value("scheme.named_color_breakdown", tuple),
        context_value("scheme.confirmed_pixel_count", int),
        context_value("scheme.residual_pixel_count", int),
        context_value("scheme.residual_distinct_colors", int),
        context_value("scheme.tonal_palettes", CorePalettesModel),
        context_value("scheme.display_pixels", DisplayPixelFrequenciesModel),
        context_value("environmental.inputs.original.raw_pixel_frequencies", list),
        context_value("token.inventory", TokenInventoryModel),
        context_value("transformation.heuristics", list),
        context_value("session", Session, validator=_session_ready_for_results),
    ),
    produces=(
        context_value("recommendations", RecommendationsPayload),
        context_value("results", dict),
    ),
)


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _token_runtime_summary(token_inventory: TokenInventoryModel) -> dict[str, int]:
    assigned_element_ids = {
        str(element_id).strip()
        for token in token_inventory
        for element_id in token.assigned_element_ids
        if str(element_id).strip()
    }
    style_refs = {
        str(property_ref).strip()
        for token in token_inventory
        for property_ref in token.source_property_refs
        if str(property_ref).strip()
    }
    color_ids = {
        str(color_id).strip()
        for token in token_inventory
        for color_id in token.source_color_ids
        if str(color_id).strip()
    }
    palette_tones = {
        f"{str(palette_id).strip()}:{int(token.tone)}"
        for token in token_inventory
        if token.tone is not None
        for palette_id in token.source_palette_ids
        if str(palette_id).strip()
    }
    return {
        "tokenized_element_count": len(assigned_element_ids),
        "tokenized_style_ref_count": len(style_refs),
        "tokenized_color_count": len(color_ids),
        "tokenized_palette_tone_count": len(palette_tones),
    }


def _prune_empty_artifact_fields(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, item in value.items():
            cleaned_item = _prune_empty_artifact_fields(item)
            if key.endswith("artifact") or key.endswith("_artifact") or key.endswith("_output"):
                if cleaned_item in ("", None, (), [], {}):
                    continue
            cleaned[key] = cleaned_item
        return cleaned
    if isinstance(value, list):
        return [_prune_empty_artifact_fields(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_prune_empty_artifact_fields(item) for item in value)
    return value


def _build_dominant_rows(color_processing: Mapping[str, object]) -> list[dict[str, object]]:
    rows_by_family: dict[str, dict[str, object]] = {}
    named_color_breakdown = color_processing.get("named_color_breakdown") or []

    for item in named_color_breakdown:
        entry = _as_mapping(item)
        if not entry:
            continue
        family_name = str(
            entry.get("family")
            or entry.get("display_name")
            or entry.get("name")
            or "Color"
        )
        percentage = float(entry.get("percentage") or 0)
        hex_value = str(entry.get("hex_value") or "#86919f")
        current = rows_by_family.get(family_name)

        if current is None:
            rows_by_family[family_name] = {
                "label": family_name,
                "hex": hex_value,
                "percentage": percentage,
                "_top_percentage": percentage,
            }
            continue

        current["percentage"] = float(current.get("percentage") or 0) + percentage
        if percentage >= float(current.get("_top_percentage") or 0):
            current["hex"] = hex_value
            current["_top_percentage"] = percentage

    if rows_by_family:
        rows = list(rows_by_family.values())
        rows.sort(key=lambda item: float(item.get("percentage") or 0), reverse=True)
        for row in rows:
            row.pop("_top_percentage", None)
        return rows

    core_palettes = _as_mapping(color_processing.get("core_palettes"))
    achromatic_palette = _as_mapping(core_palettes.get("achromatic_palette"))
    if achromatic_palette:
        rows_by_family["Neutral"] = {
            "label": str(achromatic_palette.get("display_name") or "Neutral"),
            "hex": str(achromatic_palette.get("seed_hex") or "#86919f"),
            "percentage": 0.0,
        }

    for palette in core_palettes.get("chromatic_palettes") or []:
        entry = _as_mapping(palette)
        if not entry:
            continue
        family_name = str(
            entry.get("seed_family_name")
            or entry.get("display_name")
            or entry.get("seed_display_name")
            or entry.get("seed_name")
            or "Color"
        )
        rows_by_family.setdefault(
            family_name,
            {
                "label": family_name,
                "hex": str(entry.get("seed_hex") or "#86919f"),
                "percentage": 0.0,
            },
        )

    return list(rows_by_family.values())


def _build_palette_rows(color_processing: Mapping[str, object]) -> list[dict[str, object]]:
    palette_rows: list[dict[str, object]] = []
    core_palettes = _as_mapping(color_processing.get("core_palettes"))
    achromatic_palette = _as_mapping(core_palettes.get("achromatic_palette"))

    if achromatic_palette:
        palette_rows.append(
            {
                "family_type": "achromatic",
                "label": achromatic_palette.get("display_name") or "Neutral",
                "tone_count": len(achromatic_palette.get("tones") or []),
                "tones": achromatic_palette.get("tones") or [],
            }
        )

    for palette in core_palettes.get("chromatic_palettes") or []:
        entry = _as_mapping(palette)
        if not entry:
            continue
        palette_rows.append(
            {
                "family_type": "chromatic",
                "label": entry.get("display_name") or entry.get("seed_display_name") or entry.get("seed_name"),
                "tone_count": len(entry.get("tones") or []),
                "tones": entry.get("tones") or [],
            }
        )

    return palette_rows


def _build_palette_label_map(color_processing: Mapping[str, object]) -> dict[str, str]:
    palette_labels: dict[str, str] = {}
    core_palettes = _as_mapping(color_processing.get("core_palettes"))
    achromatic_palette = _as_mapping(core_palettes.get("achromatic_palette"))

    achromatic_id = str(achromatic_palette.get("palette_id") or "").strip()
    if achromatic_id:
        palette_labels[achromatic_id] = str(
            achromatic_palette.get("display_name") or "Neutral"
        )

    for palette in core_palettes.get("chromatic_palettes") or []:
        entry = _as_mapping(palette)
        palette_id = str(entry.get("palette_id") or "").strip()
        if not palette_id:
            continue
        palette_labels[palette_id] = str(
            entry.get("display_name")
            or entry.get("seed_display_name")
            or entry.get("seed_name")
            or "Chromatic"
        )

    return palette_labels


def _iter_color_inventory_entries(color_inventory: object | None) -> tuple[object, ...]:
    if color_inventory is None:
        return ()
    raw_entries = getattr(color_inventory, "entries", color_inventory)
    if not isinstance(raw_entries, (list, tuple)):
        return ()
    return tuple(entry for entry in raw_entries if entry is not None)


def _normalize_color_value(value: object) -> str:
    return str(value or "").strip().lower()


def _nearest_tone_stop(value: float) -> int:
    return min(_TONE_STOPS, key=lambda stop: abs(stop - float(value)))


def _fallback_palette_label(palette_id: str | None) -> str:
    palette_id = str(palette_id or "").strip().lower()
    if "achromatic" in palette_id:
        return "Neutral"
    if "chromatic" in palette_id:
        return "Chromatic"
    return "Color"


def _tone_label_from_entry(
    entry: object,
    *,
    palette_labels: Mapping[str, str],
) -> str | None:
    palette_id = getattr(entry, "mapped_palette_id", None)
    mapped_tone = getattr(entry, "mapped_tone", None)
    if palette_id is None or mapped_tone is None:
        return None
    return f"{palette_labels.get(str(palette_id), _fallback_palette_label(str(palette_id)))} {int(mapped_tone)}"


def _nearest_mapped_inventory_entry(raw_value: str, entries: tuple[object, ...]) -> object | None:
    try:
        target_rgb = color_registry.format_color(raw_value, "rgb")
    except Exception:
        return None

    best_entry = None
    best_distance: int | None = None

    for entry in entries:
        palette_id = getattr(entry, "mapped_palette_id", None)
        mapped_tone = getattr(entry, "mapped_tone", None)
        candidate_rgb = getattr(entry, "rgb", None)
        if palette_id is None or mapped_tone is None or not candidate_rgb:
            continue
        distance = sum(
            (int(target_channel) - int(candidate_channel)) ** 2
            for target_channel, candidate_channel in zip(target_rgb, candidate_rgb)
        )
        if best_distance is None or distance < best_distance:
            best_entry = entry
            best_distance = distance

    return best_entry


def _fallback_tone_label(raw_value: str) -> str:
    try:
        match = nearest_web_color(raw_value)
        tone = _nearest_tone_stop(color_registry.hct_of(raw_value)[2])
        family_label = _WEB_FAMILY_DISPLAY_NAMES.get(match.group_name, match.display_name)
        return f"{family_label} {tone}"
    except Exception:
        return "Tone n/a"


def _resolve_tone_label(
    color_reference: Mapping[str, object],
    *,
    palette_labels: Mapping[str, str],
    entries_by_id: Mapping[str, object],
    entries_by_value: Mapping[str, object],
    inventory_entries: tuple[object, ...],
) -> str:
    color_id = str(color_reference.get("color_id") or "").strip()
    if color_id:
        exact_entry = entries_by_id.get(color_id)
        if exact_entry is not None:
            exact_label = _tone_label_from_entry(exact_entry, palette_labels=palette_labels)
            if exact_label is not None:
                return exact_label

    raw_value = str(
        color_reference.get("css")
        or color_reference.get("hex")
        or color_reference.get("hex_value")
        or ""
    ).strip()
    if not raw_value:
        return "Tone n/a"

    exact_value_entry = entries_by_value.get(_normalize_color_value(raw_value))
    if exact_value_entry is not None:
        exact_value_label = _tone_label_from_entry(exact_value_entry, palette_labels=palette_labels)
        if exact_value_label is not None:
            return exact_value_label

    nearest_entry = _nearest_mapped_inventory_entry(raw_value, inventory_entries)
    if nearest_entry is not None:
        nearest_label = _tone_label_from_entry(nearest_entry, palette_labels=palette_labels)
        if nearest_label is not None:
            return nearest_label

    return _fallback_tone_label(raw_value)


def _build_contrast_rows(
    results: Mapping[str, object],
    *,
    color_inventory: object | None,
) -> list[dict[str, object]]:
    color_processing = _as_mapping(results.get("color_processing"))
    palette_labels = _build_palette_label_map(color_processing)
    inventory_entries = _iter_color_inventory_entries(color_inventory)
    entries_by_id = {
        str(getattr(entry, "color_id", "")).strip(): entry
        for entry in inventory_entries
        if str(getattr(entry, "color_id", "")).strip()
    }
    entries_by_value = {
        _normalize_color_value(candidate_value): entry
        for entry in inventory_entries
        for candidate_value in (
            getattr(entry, "value", None),
            getattr(entry, "hex_value", None),
        )
        if _normalize_color_value(candidate_value)
        and getattr(entry, "mapped_palette_id", None) is not None
        and getattr(entry, "mapped_tone", None) is not None
    }
    tone_label_cache: dict[str, str] = {}
    contrast = _as_mapping(_as_mapping(results.get("accessibility")).get("contrast"))
    rows: list[dict[str, object]] = []

    for item in contrast.get("issues") or []:
        issue = _as_mapping(item)
        foreground = _as_mapping(issue.get("foreground"))
        background = _as_mapping(issue.get("background"))
        foreground_value = str(
            foreground.get("css")
            or foreground.get("hex")
            or foreground.get("hex_value")
            or ""
        ).strip()
        background_value = str(
            background.get("css")
            or background.get("hex")
            or background.get("hex_value")
            or ""
        ).strip()

        if foreground_value not in tone_label_cache:
            tone_label_cache[foreground_value] = _resolve_tone_label(
                foreground,
                palette_labels=palette_labels,
                entries_by_id=entries_by_id,
                entries_by_value=entries_by_value,
                inventory_entries=inventory_entries,
            )
        if background_value not in tone_label_cache:
            tone_label_cache[background_value] = _resolve_tone_label(
                background,
                palette_labels=palette_labels,
                entries_by_id=entries_by_id,
                entries_by_value=entries_by_value,
                inventory_entries=inventory_entries,
            )

        rows.append(
            {
                "selector": str(issue.get("selector") or "Unmapped selector"),
                "contrast_ratio": float(issue.get("contrast_ratio") or 0.0),
                "required_ratio": float(issue.get("required_ratio") or 0.0),
                "foreground_hex": str(
                    foreground.get("hex") or foreground.get("hex_value") or "#ffffff"
                ),
                "background_hex": str(
                    background.get("hex") or background.get("hex_value") or "#000000"
                ),
                "foreground_tone_label": tone_label_cache[foreground_value],
                "background_tone_label": tone_label_cache[background_value],
            }
        )

    return rows


def _build_change_history_groups(heuristics: object) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []

    for item in heuristics or []:
        heuristic = _as_mapping(item)
        if not heuristic:
            continue

        title = str(heuristic.get("nombre") or "Transformation")
        summary = str(heuristic.get("recomendacion") or "").strip()
        changes: list[dict[str, object]] = []
        notes: list[str] = []

        for comparison in heuristic.get("comparativas") or []:
            entry = _as_mapping(comparison)
            if not entry:
                continue

            before_rgb = str(entry.get("antes") or "").strip()
            after_rgb = str(entry.get("despues") or "").strip()
            savings_value = entry.get("ahorro")
            try:
                savings_float = float(savings_value)
                savings_label = f"{savings_float:.2f}% ahorro"
            except Exception:
                savings_label = None

            changes.append(
                {
                    "name": str(entry.get("nombre") or "Component"),
                    "before_rgb": before_rgb,
                    "after_rgb": after_rgb,
                    "before_css": f"rgb({before_rgb})" if before_rgb else "",
                    "after_css": f"rgb({after_rgb})" if after_rgb else "",
                    "savings_label": savings_label,
                }
            )

        if not changes:
            notes = [
                str(detail).strip()
                for detail in (heuristic.get("detalles") or [])
                if str(detail).strip()
            ]

        if not changes and not notes:
            continue

        groups.append(
            {
                "title": title,
                "summary": summary,
                "change_count": len(changes),
                "changes": changes,
                "notes": notes,
            }
        )

    return groups


def _build_results_view(
    results: Mapping[str, object],
    *,
    color_inventory: object | None = None,
) -> dict[str, object]:
    color_processing = _as_mapping(results.get("color_processing"))
    dominant_rows = _build_dominant_rows(color_processing)
    top_three_percentage = sum(float((item or {}).get("percentage") or 0) for item in dominant_rows[:3])
    carbon_footprint = results.get("carbon_footprint")
    environmental_footprint = results.get("environmental_co2eq_per_use")
    initial_reduction = 0.0
    if isinstance(carbon_footprint, (int, float)) and isinstance(environmental_footprint, (int, float)):
        initial_reduction = float(carbon_footprint) - float(environmental_footprint)

    return {
        "initial_reduction": initial_reduction,
        "dominant_rows": dominant_rows,
        "dominant_color_count": len(dominant_rows),
        "top_three_percentage": top_three_percentage,
        "palette_rows": _build_palette_rows(color_processing),
        "contrast_rows": _build_contrast_rows(results, color_inventory=color_inventory),
        "change_history_groups": _build_change_history_groups(results.get("heuristics") or []),
    }


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    context.trace.add_stage_event(CONTRACT.name, "start")
    session = context.get("session")
    output_dir = session.output_dir
    artifacts_dir = session.artifacts_dir
    session_dirname = session.session_dirname
    zip_output_path, zip_filename = create_output_bundle(
        source_dir=output_dir,
        bundle_dir=artifacts_dir,
        bundle_name=session.bundle_name,
    )
    download_path = session.download_path
    context.set("recommendations", RecommendationsPayload(items=(), summary=None))
    context.trace.add_step("transformed.zip_created", {"zip_output_path": zip_output_path})

    before = context.get("environmental.assessment.before", {})
    after = context.get("environmental.assessment.after", {})
    savings = context.get("environmental.assessment.savings")
    named_color_breakdown = [dict(item) for item in (context.get("scheme.named_color_breakdown") or ())]
    tonal_palettes = context.get("scheme.tonal_palettes")
    scheme_colors = tuple(context.get("scheme.colors"))
    scheme_color_inventory = build_inventory_from_scheme_colors(scheme_colors)
    display_frequencies = context.get("scheme.display_pixels")
    raw_pixel_frequencies = context.get("environmental.inputs.original.raw_pixel_frequencies") or []
    token_inventory = context.get("token.inventory")
    token_runtime = _token_runtime_summary(token_inventory)
    original_snapshot_metadata = dict(session.original_snapshot_metadata or {})
    original_screenshot = Path(session.original_screenshot_path).name
    transformed_screenshot = Path(session.transformed_screenshot_path).name
    pixel_frequency_rows = display_frequencies.to_rows()
    contrast_report = (
        context.get("derived.contrast_report")
        if context.has("derived.contrast_report")
        else None
    )
    contrast_payload = contrast_report.to_dict() if contrast_report is not None else {"count": 0, "issues": []}
    effect_color_report = (
        context.get("derived.effect_color_report")
        if context.has("derived.effect_color_report")
        else None
    )
    effect_color_payload = (
        effect_color_report.to_dict()
        if effect_color_report is not None
        else {"count": 0, "entries": [], "by_property": []}
    )

    results = {
        "total_current": before.current_a,
        "carbon_footprint": before.co2eq_per_use,
        "energy_wh": before.energy_wh,
        "environmental_energy_wh": after.energy_wh,
        "environmental_co2eq_per_use": after.co2eq_per_use,
        "session_id": session.session_id,
        "session_dirname": session_dirname,
        "html_name": session.input_html_name,
        "heuristics": context.get("transformation.heuristics", []),
        "debug": context.trace.to_dict() if context.trace else None,
        "debug_screenshots": {
            "original": original_screenshot,
            "environmental": transformed_screenshot,
        },
        "recommendations": context.get("recommendations").to_dict(),
        "download_url": download_path,
        "environmental_assessment": {
            "before": before.to_dict(),
            "after": after.to_dict(),
            "savings": savings.to_dict(),
        },
        "render_snapshot": {
            "node_count": original_snapshot_metadata.get("nodeCount"),
            "palette_color_count": len(scheme_colors),
        },
        "color_processing": {
            "palette_preview_location": "artifacts",
            "pixel_color_frequency_count": len(pixel_frequency_rows),
            "pixel_color_statistics_count": len(color_frequency_to_statistics(pixel_frequency_rows)),
            "pixel_color_frequency_raw_count": len(raw_pixel_frequencies),
            "named_color_breakdown": named_color_breakdown,
            "confirmed_pixel_count": context.get("scheme.confirmed_pixel_count"),
            "residual_pixel_count": context.get("scheme.residual_pixel_count"),
            "residual_distinct_colors": context.get("scheme.residual_distinct_colors"),
            "core_palettes": tonal_palettes.to_dict(),
        },
        "token_processing": {
            "token_count": len(token_inventory or ()),
            "foundation_token_count": sum(
                1
                for token in (token_inventory or ())
                if getattr(token, "is_foundation", False)
            ),
            "semantic_token_count": sum(
                1
                for token in (token_inventory or ())
                if getattr(token, "is_semantic", False)
            ),
            "component_token_count": sum(
                1
                for token in (token_inventory or ())
                if getattr(token, "is_component", False)
            ),
            "failed_token_count": len(
                [
                    token
                    for token in (token_inventory or ())
                    if getattr(token, "has_failed_validations", False)
                ]
            ),
            "tokenized_element_count": token_runtime["tokenized_element_count"],
            "tokenized_style_ref_count": token_runtime["tokenized_style_ref_count"],
            "tokenized_color_count": token_runtime["tokenized_color_count"],
            "tokenized_palette_tone_count": token_runtime["tokenized_palette_tone_count"],
        },
        "accessibility": {
            "contrast": {
                "issue_count": int(contrast_payload.get("count") or 0),
                "issues": contrast_payload.get("issues") or [],
                "linked_issue_count": sum(
                    1
                    for issue in (contrast_payload.get("issues") or [])
                    if issue.get("element_id")
                ),
            }
        },
        "effect_colors": {
            "entry_count": int(effect_color_payload.get("count") or 0),
            "entries": effect_color_payload.get("entries") or [],
            "properties": effect_color_payload.get("by_property") or [],
        },
    }
    results["view"] = _build_results_view(
        results,
        color_inventory=scheme_color_inventory,
    )
    results = _prune_empty_artifact_fields(results)
    context.set("results", results)

    save_json(session.results_json_path, results, indent=4)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "results_path": session.results_json_path,
            "bundle_name": zip_filename,
        },
    )
    return context
