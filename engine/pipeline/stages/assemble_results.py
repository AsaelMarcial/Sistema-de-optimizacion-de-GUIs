from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath
import re

from engine.adapters.file_system.file_manager import create_output_bundle
from engine.adapters.utils.pixel import dominant_color_percentages
from engine.domain.data.web_colors import nearest_web_color
from engine.domain.enums.types.elements import PropertyClassification
from engine.domain.models.color import ColorCatalog
from engine.domain.models.environmental_assessment.assessment import (
    EnvironmentalAssessmentModel,
    EnvironmentalSavingsModel,
)
from engine.domain.models.palette import CorePalettesModel
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import AFTER_SCREENSHOT, BEFORE_SCREENSHOT, FilePath, Session
from engine.domain.models.token import TokenInventoryModel
from engine.adapters.color_service import color_registry
from engine.pipeline.context import PipelineContext, RecommendationsPayload
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.project_uploaded import has_single_html, single_html_file

_TONE_STOPS = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 98, 99, 100)
_EFFECT_COLOR_PROPERTIES = (
    "background-image",
    "text-shadow",
    "box-shadow",
    "filter",
)
_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_FUNCTION_COLOR_RE = re.compile(r"(?:rgba?|hsla?)\([^)]+\)", re.IGNORECASE)


def _session_ready_for_results(session: Session) -> bool:
    return bool(session.session_id.strip()) and has_single_html(session.file_paths)

CONTRACT = StageContract(
    name="assemble_results",
    requires=(
        context_value(K.ENVIRONMENTAL_BEFORE_ASSESSMENT, EnvironmentalAssessmentModel),
        context_value(K.ENVIRONMENTAL_AFTER_ASSESSMENT, EnvironmentalAssessmentModel),
        context_value(K.ENVIRONMENTAL_SAVINGS, EnvironmentalSavingsModel),
        context_value(K.COLOR_CATALOG, ColorCatalog),
        context_value(K.SCHEME_NAMED_COLOR_BREAKDOWN, tuple),
        context_value(K.SCHEME_TONAL_PALETTES, CorePalettesModel),
        context_value(K.ENVIRONMENTAL_BEFORE_COLOR_HISTOGRAM, list),
        context_value(K.PROTOTYPE_STRUCTURE, PrototypeStructure),
        context_value(K.DERIVED_RAW_SNAPSHOT_METADATA, dict),
        context_value(K.TOKEN_INVENTORY, TokenInventoryModel),
        context_value(K.TRANSFORMATION_HEURISTICS, list),
        context_value(K.SESSION, Session, validator=_session_ready_for_results),
    ),
    produces=(
        context_value(K.RECOMMENDATIONS, RecommendationsPayload),
        context_value(K.RESULTS, dict),
    ),
)


def _as_mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _token_runtime_summary(
    prototype_structure: PrototypeStructure,
    color_entries: tuple[object, ...],
) -> dict[str, int]:
    assigned_element_ids = {
        element.node_id
        for element in prototype_structure
        if element.token_ids
    }
    style_refs = {
        (
            f"{property_model.style_id}:{property_model.declared_property or property_model.name}"
            if property_model.style_id
            else f"{element.node_id}:{property_model.name}"
        )
        for element in prototype_structure
        for property_model in element.properties
        if property_model.token_ids or property_model.applied_token_id
    }
    color_ids = {
        str(getattr(color, "color_id", "")).strip()
        for color in color_entries
        if getattr(color, "token_ids", ()) or getattr(color, "foundation_token_id", None)
        if str(getattr(color, "color_id", "")).strip()
    }
    palette_tones = {
        f"{str(getattr(color, 'mapped_palette_id')).strip()}:{int(getattr(color, 'mapped_tone'))}"
        for color in color_entries
        if (getattr(color, "token_ids", ()) or getattr(color, "foundation_token_id", None))
        and getattr(color, "mapped_palette_id", None) is not None
        and getattr(color, "mapped_tone", None) is not None
    }
    return {
        "tokenized_element_count": len(assigned_element_ids),
        "tokenized_style_ref_count": len(style_refs),
        "tokenized_color_count": len(color_ids),
        "tokenized_palette_tone_count": len(palette_tones),
    }


def _extract_effect_color_tokens(value: str) -> tuple[str, ...]:
    normalized = str(value or "").strip()
    if not normalized:
        return ()

    tokens: list[str] = []
    for token in _HEX_COLOR_RE.findall(normalized):
        if token not in tokens:
            tokens.append(token)
    for token in _FUNCTION_COLOR_RE.findall(normalized):
        if token not in tokens:
            tokens.append(token)
    return tuple(tokens)


def _effect_colors_payload(
    prototype_structure: PrototypeStructure,
    colors_inventory: ColorCatalog,
) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    entry_index = 0

    for element in prototype_structure:
        for property_model in prototype_structure.properties_for(element):
            if (
                property_model.classification != PropertyClassification.EFFECT
                and property_model.name not in _EFFECT_COLOR_PROPERTIES
            ):
                continue

            effect_colors = _extract_effect_color_tokens(property_model.value)
            if not effect_colors:
                continue

            color_rows: list[dict[str, object]] = []
            seen_signatures: set[tuple[str, float]] = set()
            for token in effect_colors:
                try:
                    hex_value = color_registry.format_color(token, "hex")
                    alpha = color_registry.alpha_of(token)
                except Exception:
                    continue

                signature = (hex_value, round(alpha, 4))
                if signature in seen_signatures:
                    continue
                seen_signatures.add(signature)

                color_entry = colors_inventory.entry_by_value(token)
                color_payload: dict[str, object] = {
                    "value": token,
                    "hex": hex_value,
                    "alpha": round(alpha, 4),
                }
                if color_entry is not None:
                    color_payload["color_id"] = color_entry.color_id
                color_rows.append(color_payload)

            if not color_rows:
                continue

            entry_index += 1
            payload: dict[str, object] = {
                "effect_id": f"effect-{entry_index}",
                "element_id": element.node_id,
                "tag_name": element.tag_name,
                "property_name": str(property_model.name),
                "resolved_value": property_model.value,
                "colors": color_rows,
            }
            if element.selector is not None:
                payload["selector_hint"] = element.selector
            if property_model.style_id is not None:
                payload["style_id"] = property_model.style_id
            if property_model.declaration_id is not None:
                payload["declaration_id"] = property_model.declaration_id
            if property_model.declared_property is not None:
                payload["declared_property"] = str(property_model.declared_property)
            entries.append(payload)

    by_property: dict[str, dict[str, object]] = {}
    for entry in entries:
        property_name = str(entry.get("property_name") or "")
        bucket = by_property.setdefault(
            property_name,
            {
                "property_name": property_name,
                "entry_count": 0,
                "distinct_hex_values": set(),
            },
        )
        bucket["entry_count"] = int(bucket["entry_count"]) + 1
        distinct_values = bucket["distinct_hex_values"]
        if isinstance(distinct_values, set):
            for color in entry.get("colors") or ():
                if isinstance(color, Mapping) and color.get("hex"):
                    distinct_values.add(str(color["hex"]))

    property_rows = [
        {
            "property_name": property_name,
            "entry_count": int(bucket["entry_count"]),
            "distinct_color_count": (
                len(bucket["distinct_hex_values"])
                if isinstance(bucket["distinct_hex_values"], set)
                else 0
            ),
        }
        for property_name, bucket in by_property.items()
    ]
    property_rows.sort(key=lambda item: (-int(item["entry_count"]), str(item["property_name"])))
    return {
        "count": len(entries),
        "entries": entries,
        "by_property": property_rows,
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
    dominant_colors = color_processing.get("dominant_color_percentages") or []
    if dominant_colors:
        rows: list[dict[str, object]] = []
        for item in dominant_colors:
            entry = _as_mapping(item)
            color = entry.get("color")
            if color is None:
                continue
            try:
                rgb = tuple(int(channel) for channel in color)  # type: ignore[union-attr]
                match = nearest_web_color(rgb)
                rows.append(
                    {
                        "label": match.family_display_name,
                        "hex": color_registry.format_color(rgb, "hex"),
                        "percentage": float(entry.get("percentage") or 0.0),
                        "count": int(entry.get("count") or 0),
                    }
                )
            except Exception:
                continue
        if rows:
            return rows

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
        return f"{match.family_display_name} {tone}"
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
    session = context.get(K.SESSION)
    output_dir = session.build_path("after")
    artifacts_dir = session.build_path("artifacts")
    session_dirname = artifacts_dir.parent.name
    html_file = single_html_file(session.file_paths)
    project_root = session.project_root_file_path()
    bundle_file = FilePath(
        f"{project_root.name}.zip" if project_root.name else f"{html_file.relative_path.stem}.zip",
    )
    bundle_name = bundle_file.name
    zip_output_path, zip_filename = create_output_bundle(
        source_dir=output_dir,
        bundle_dir=artifacts_dir,
        bundle_name=bundle_name,
    )
    download_path = str(PurePosixPath("/sessions", session_dirname, "artifacts", bundle_name))
    context.set(K.RECOMMENDATIONS, RecommendationsPayload(items=(), summary=None))
    context.trace.add_step("transformed.zip_created", {"zip_output_path": zip_output_path})

    before = context.get(K.ENVIRONMENTAL_BEFORE_ASSESSMENT, {})
    after = context.get(K.ENVIRONMENTAL_AFTER_ASSESSMENT, {})
    savings = context.get(K.ENVIRONMENTAL_SAVINGS)
    named_color_breakdown = [dict(item) for item in (context.get(K.SCHEME_NAMED_COLOR_BREAKDOWN) or ())]
    tonal_palettes = context.get(K.SCHEME_TONAL_PALETTES)
    colors_inventory = context.get(K.COLOR_CATALOG)
    color_entries = tuple(colors_inventory)
    prototype_structure = context.get(K.PROTOTYPE_STRUCTURE)
    environmental_before_color_histogram = context.get(K.ENVIRONMENTAL_BEFORE_COLOR_HISTOGRAM) or []
    token_inventory = context.get(K.TOKEN_INVENTORY)
    token_runtime = _token_runtime_summary(prototype_structure, color_entries)
    before_snapshot_metadata = dict(context.get(K.DERIVED_RAW_SNAPSHOT_METADATA) or {})
    before_screenshot = BEFORE_SCREENSHOT.name
    after_screenshot = AFTER_SCREENSHOT.name
    contrast_report = (
        context.get(K.DERIVED_CONTRAST_REPORT)
        if context.has(K.DERIVED_CONTRAST_REPORT)
        else None
    )
    contrast_payload = contrast_report.to_dict() if contrast_report is not None else {"count": 0, "issues": []}
    effect_color_payload = _effect_colors_payload(prototype_structure, colors_inventory)

    results = {
        "total_current": before.current_a,
        "carbon_footprint": before.co2eq_per_use,
        "energy_wh": before.energy_wh,
        "environmental_energy_wh": after.energy_wh,
        "environmental_co2eq_per_use": after.co2eq_per_use,
        "session_id": session.session_id,
        "session_dirname": session_dirname,
        "html_name": html_file.name,
        "heuristics": context.get(K.TRANSFORMATION_HEURISTICS, []),
        "debug": context.trace.to_dict() if context.trace else None,
        "debug_screenshots": {
            "before": before_screenshot,
            "after": after_screenshot,
        },
        "recommendations": context.get(K.RECOMMENDATIONS).to_dict(),
        "download_url": download_path,
        "environmental_assessment": {
            "before": before.to_dict(),
            "after": after.to_dict(),
            "savings": savings.to_dict(),
        },
        "render_snapshot": {
            "node_count": before_snapshot_metadata.get("nodeCount"),
            "palette_color_count": len(colors_inventory),
        },
        "color_processing": {
            "palette_preview_location": "artifacts",
            "dominant_color_percentages": dominant_color_percentages(
                environmental_before_color_histogram,
                limit=10,
            ),
            "named_color_breakdown": named_color_breakdown,
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
        color_inventory=colors_inventory,
    )
    results = _prune_empty_artifact_fields(results)
    context.set(K.RESULTS, results)

    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "bundle_name": zip_filename,
        },
    )
    return context
