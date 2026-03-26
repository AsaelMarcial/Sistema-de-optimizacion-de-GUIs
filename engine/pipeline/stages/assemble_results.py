from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from engine.adapters.file_system.file_handler import create_output_bundle
from engine.adapters.utils.io import save_json
from engine.domain.data.web_colors import nearest_web_color
from engine.domain.models.environmental_assessment.assessment import (
    EnvironmentalAssessmentModel,
    EnvironmentalSavingsModel,
)
from engine.domain.models.session import ProjectStateModel
from engine.domain.utils.coloraide import color_to_rgb_tuple, hct_coords
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

CONTRACT = StageContract(
    name="assemble_results",
    requires=(
        context_value("environmental.assessment.before", EnvironmentalAssessmentModel),
        context_value("environmental.assessment.after", EnvironmentalAssessmentModel),
        context_value("environmental.assessment.savings", EnvironmentalSavingsModel),
        context_value("scheme.color_scheme"),
        context_value("transformation.heuristics", list),
        context_value("session.output.paths.results_json", str, validator=lambda value: bool(value.strip())),
    ),
    produces=(
        context_value("recommendations", RecommendationsPayload),
        context_value("results", dict),
        context_value("session.output.project", ProjectStateModel),
        context_value("session.output.bundle.path", str, validator=lambda value: bool(value.strip())),
        context_value("session.output.bundle.name", str, validator=lambda value: bool(value.strip())),
        context_value(
            "session.output.bundle.download_path",
            str,
            validator=lambda value: bool(value.strip()),
        ),
    ),
)


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


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
        target_rgb = color_to_rgb_tuple(raw_value)
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
        tone = _nearest_tone_stop(hct_coords(raw_value)[2])
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
    output_dir = context.get("session.output.paths.output_dir", "")
    artifacts_dir = context.get("session.output.paths.artifacts_dir", "")
    session_dirname = context.get("session.output.dirname", "")
    input_project = context.get("session.input.project")
    source_upload_name = Path(input_project.upload_path or input_project.html_name).name
    bundle_name = (
        source_upload_name
        if source_upload_name.lower().endswith(".zip")
        else f"{Path(source_upload_name).stem}.zip"
    )
    zip_output_path, zip_filename = create_output_bundle(
        source_dir=output_dir,
        bundle_dir=artifacts_dir,
        bundle_name=bundle_name,
    )
    download_path = f"/sessions/{session_dirname}/artifacts/{zip_filename}"
    context.set("session.output.bundle.path", zip_output_path)
    context.set("session.output.bundle.name", zip_filename)
    context.set("session.output.bundle.download_path", download_path)
    output_project = context.get("session.output.project")
    context.set(
        "session.output.project",
        ProjectStateModel.build(
            directory=output_project.directory,
            upload_path=output_project.upload_path,
            base_path=output_project.base_path,
            normalized_base_path=output_project.normalized_base_path,
            html_path=output_project.html_path,
            html_name=output_project.html_name,
            html_content=output_project.html_content,
            download_path=download_path,
            bundle_path=zip_output_path,
        ),
    )
    context.set("recommendations", RecommendationsPayload(items=(), summary=None))
    context.trace.add_step("transformed.zip_created", {"zip_output_path": zip_output_path})

    before = context.get("environmental.assessment.before", {})
    after = context.get("environmental.assessment.after", {})
    savings = context.get("environmental.assessment.savings")
    color_scheme_model = context.get("scheme.color_scheme")
    color_scheme = color_scheme_model.to_dict()
    original_snapshot = context.get("session.artifacts.original.snapshot")
    original_snapshot_metadata = context.get("session.artifacts.original.snapshot_metadata", {})
    original_screenshot = Path(context.get("session.artifacts.original.screenshot", "")).name
    transformed_screenshot = Path(context.get("session.artifacts.output.screenshot", "")).name
    display_frequencies = context.get("session.artifacts.original.pixel_frequencies_display")
    pixel_frequency_rows = display_frequencies.to_rows()
    contrast_report = (
        context.get("inventory.contrast_report")
        if context.has("inventory.contrast_report")
        else None
    )
    contrast_payload = contrast_report.to_dict() if contrast_report is not None else {"count": 0, "issues": []}
    effect_color_report = (
        context.get("inventory.effect_color_report")
        if context.has("inventory.effect_color_report")
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
        "session_id": context.get("session.output.id", ""),
        "session_dirname": session_dirname,
        "html_name": context.get("session.input.html.name", ""),
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
            "artifact": Path(context.get("session.output.paths.original.snapshot_json", "")).name,
            "node_count": (
                original_snapshot.metadata.get("nodeCount")
                if original_snapshot is not None
                else original_snapshot_metadata.get("nodeCount")
            ),
            "palette_color_count": len(context.get("color.inventory") or ()),
        },
        "color_processing": {
            "artifact": Path(context.get("session.output.paths.color_scheme_json", "")).name,
            "palette_preview_artifact": Path(context.get("scheme.preview.path", "")).name,
            "palette_preview_output": Path(context.get("scheme.preview.path", "")).name,
            "palette_preview_location": "artifacts",
            "pixel_color_frequency_count": len(pixel_frequency_rows),
            "pixel_color_statistics_count": len(color_frequency_to_statistics(pixel_frequency_rows)),
            "pixel_color_frequency_raw_count": len(
                context.get("session.artifacts.original.pixel_frequencies_raw", [])
            ),
            "named_color_breakdown": color_scheme.get("named_color_breakdown") or [],
            "confirmed_pixel_count": color_scheme.get("confirmed_pixel_count"),
            "residual_pixel_count": color_scheme.get("residual_pixel_count"),
            "core_palettes": color_scheme.get("core_palettes") or {},
        },
        "token_processing": {
            "artifact": Path(context.get("session.output.paths.tokens_original_json", "")).name,
            "graph_artifact": Path(context.get("session.output.paths.inventory_graph_json", "")).name,
            "token_count": len(context.get("token.inventory") or ()),
            "foundation_token_count": sum(
                1
                for token in (context.get("token.inventory") or ())
                if getattr(token, "is_foundation", False)
            ),
            "semantic_token_count": sum(
                1
                for token in (context.get("token.inventory") or ())
                if getattr(token, "is_semantic", False)
            ),
            "component_token_count": sum(
                1
                for token in (context.get("token.inventory") or ())
                if getattr(token, "is_component", False)
            ),
            "failed_token_count": len(
                [
                    token
                    for token in (context.get("token.inventory") or ())
                    if getattr(token, "has_failed_validations", False)
                ]
            ),
            "tokenized_element_count": len(
                getattr(context.get("inventory.graph"), "element_to_token_ids", {}) or {}
            )
            if context.has("inventory.graph")
            else 0,
            "tokenized_style_ref_count": len(
                getattr(context.get("inventory.graph"), "style_ref_to_token_ids", {}) or {}
            )
            if context.has("inventory.graph")
            else 0,
            "tokenized_color_count": len(
                getattr(context.get("inventory.graph"), "color_to_token_ids", {}) or {}
            )
            if context.has("inventory.graph")
            else 0,
            "tokenized_palette_tone_count": len(
                getattr(context.get("inventory.graph"), "palette_tone_to_token_ids", {}) or {}
            )
            if context.has("inventory.graph")
            else 0,
        },
        "accessibility": {
            "contrast": {
                "artifact": Path(
                    context.get("session.output.paths.original.contrast_report_json", "")
                ).name,
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
            "artifact": Path(
                context.get("session.output.paths.original.effect_color_report_json", "")
            ).name,
            "entry_count": int(effect_color_payload.get("count") or 0),
            "entries": effect_color_payload.get("entries") or [],
            "properties": effect_color_payload.get("by_property") or [],
        },
    }
    results["view"] = _build_results_view(
        results,
        color_inventory=(
            context.get("color.inventory")
            if context.has("color.inventory")
            else None
        ),
    )
    context.set("results", results)

    save_json(context.get("session.output.paths.results_json"), results, indent=4)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "results_path": context.get("session.output.paths.results_json"),
            "bundle_name": zip_filename,
        },
    )
    return context
