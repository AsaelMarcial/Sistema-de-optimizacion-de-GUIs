from __future__ import annotations

from typing import Any
from pprint import pformat

from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.debug_trace import DebugTrace
from engine.pipeline.result import PipelineResult
from engine.pipeline.stage_contract import PipelineContractError, StageContract, validate_produces, validate_requires
from engine.pipeline.stages.capture_original_state import CONTRACT as CAPTURE_ORIGINAL_STATE_CONTRACT
from engine.pipeline.stages.capture_original_state import run_stage as run_capture_original_state_stage
from engine.pipeline.stages.assess_enviromental_impact import CONTRACT as ASSESS_ENVIROMENTAL_IMPACT_CONTRACT
from engine.pipeline.stages.assess_enviromental_impact import run_stage as run_assess_enviromental_impact_stage
from engine.pipeline.stages.close_page_builder import CONTRACT as CLOSE_PAGE_BUILDER_CONTRACT
from engine.pipeline.stages.close_page_builder import run_stage as run_close_page_builder_stage
from engine.pipeline.stages.data_processor import CONTRACT as DATA_PROCESSOR_CONTRACT
from engine.pipeline.stages.data_processor import run_stage as run_data_processor_stage
from engine.pipeline.stages.prepare_project_session import CONTRACT as PREPARE_PROJECT_SESSION_CONTRACT
from engine.pipeline.stages.prepare_project_session import run_stage as run_prepare_project_session_stage
from engine.pipeline.stages.start_page_builder import CONTRACT as START_PAGE_BUILDER_CONTRACT
from engine.pipeline.stages.start_page_builder import run_stage as run_start_page_builder_stage
from engine.pipeline.stages.transform_design import CONTRACT as TRANSFORM_DESIGN_CONTRACT
from engine.pipeline.stages.transform_design import run_stage as run_transform_design_stage
_STAGES: tuple[tuple[StageContract, Any], ...] = (
    (START_PAGE_BUILDER_CONTRACT, run_start_page_builder_stage),
    (CAPTURE_ORIGINAL_STATE_CONTRACT, run_capture_original_state_stage),
    (DATA_PROCESSOR_CONTRACT, run_data_processor_stage),
    (TRANSFORM_DESIGN_CONTRACT, run_transform_design_stage),
    (ASSESS_ENVIROMENTAL_IMPACT_CONTRACT, run_assess_enviromental_impact_stage),
    (CLOSE_PAGE_BUILDER_CONTRACT, run_close_page_builder_stage),
)


# DEBUG TEMPORAL: serializa paletas para el fallback minimo de results.html.
# Eliminar cuando assemble_results vuelva a ser parte del pipeline completo.
def _palette_rows(color_scheme: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for palette in (getattr(color_scheme, "get_palettes", lambda: {})() or {}).values():
        tones: list[dict[str, Any]] = []
        for tone in getattr(palette, "tones", ()) or ():
            color = getattr(tone, "color", None)
            try:
                hex_value = color.convert("srgb").to_string(hex=True)
            except Exception:
                hex_value = "#000000"
            tone_value = int(getattr(tone, "value", 0))
            tones.append(
                {
                    "tone": tone_value,
                    "hex_value": hex_value,
                    "is_light": tone_value >= 80,
                }
            )
        rows.append(
            {
                "family_type": "achromatic" if getattr(palette, "name", "") == "Neutral" else "chromatic",
                "label": getattr(palette, "name", "Color"),
                "tone_count": len(tones),
                "tones": tones,
            }
        )
    return rows


def _color_css(color: Any) -> str:
    try:
        srgb = color.convert("srgb").fit("srgb")
        alpha = float(srgb.alpha(nans=False))
        return srgb.to_string(comma=True, alpha=alpha < 0.999)
    except Exception:
        return "rgb(0, 0, 0)"


def _color_rgb(color: Any) -> str:
    try:
        srgb = color.convert("srgb").fit("srgb")
        red, green, blue = srgb.coords(nans=False)
        return f"{round(float(red) * 255)}, {round(float(green) * 255)}, {round(float(blue) * 255)}"
    except Exception:
        return "0, 0, 0"


def _change_history_groups(summary: Any) -> list[dict[str, Any]]:
    if summary is None:
        return []

    iter_changes = getattr(summary, "iter_changes", None)
    changes_source = iter_changes() if callable(iter_changes) else getattr(summary, "changes", ())
    changes: list[dict[str, Any]] = []

    for change in changes_source or ():
        before_color = getattr(change, "before_color", None)
        after_color = getattr(change, "after_color", None)
        changes.append(
            {
                "name": f"Ajuste {getattr(change, 'change_id', len(changes) + 1)}",
                "savings_label": "",
                "before_css": _color_css(before_color),
                "after_css": _color_css(after_color),
                "before_rgb": _color_rgb(before_color),
                "after_rgb": _color_rgb(after_color),
                "before_code": getattr(change, "before_code", ""),
                "after_code": getattr(change, "after_code", ""),
            }
        )

    if not changes:
        return []

    return [
        {
            "title": "Transformacion de color",
            "summary": "Cambios registrados desde Summary durante transform_design.",
            "change_count": len(changes),
            "changes": changes,
        }
    ]


# DEBUG TEMPORAL: imprime Summary en results.html para validar data_processor.
# Eliminar cuando assemble_results vuelva a consultar Summary directamente.
def _debug_summary_text(summary: Any) -> str:
    if summary is None:
        return ""

    overviews: dict[str, Any] = {}
    summary_overviews = getattr(summary, "overviews", ())
    if callable(summary_overviews):
        summary_overviews = summary_overviews().values()
    for overview in summary_overviews or ():
        overviews[getattr(overview, "name", "")] = _debug_value(getattr(overview, "data", None))

    contrast_issues: list[dict[str, Any]] = []
    summary_contrast_issues = getattr(summary, "contrast_issues", ())
    if callable(summary_contrast_issues):
        summary_contrast_issues = summary_contrast_issues().values()
    for issue in summary_contrast_issues or ():
        contrast_issues.append(
            {
                "issue_id": getattr(issue, "issue_id", None),
                "backend_node_id": getattr(issue, "backend_node_id", None),
                "contrast_ratio": getattr(issue, "contrast_ratio", None),
                "required_ratio": getattr(issue, "required_ratio", None),
                "is_large_text": getattr(issue, "is_large_text", None),
                "foreground": _debug_value(getattr(issue, "foreground", None)),
                "background": _debug_value(getattr(issue, "background", None)),
            }
        )

    changes: list[dict[str, Any]] = []
    iter_changes = getattr(summary, "iter_changes", None)
    summary_changes = iter_changes() if callable(iter_changes) else getattr(summary, "changes", ())
    for change in summary_changes or ():
        changes.append(
            {
                "change_id": getattr(change, "change_id", None),
                "before_code": getattr(change, "before_code", None),
                "after_code": getattr(change, "after_code", None),
                "before_color": _debug_value(getattr(change, "before_color", None)),
                "after_color": _debug_value(getattr(change, "after_color", None)),
            }
        )

    return pformat(
        {
            "overviews": overviews,
            "contrast_issues": contrast_issues,
            "changes": changes,
        },
        sort_dicts=False,
        width=120,
    )


# DEBUG TEMPORAL: imprime DOM_TREE en results.html para validar capture_original_state.
# Eliminar cuando assemble_results vuelva a consultar DOM_TREE directamente.
def _debug_dom_tree_text(root: Any) -> str:
    if root is None:
        return ""

    rows: list[dict[str, Any]] = []
    for element in getattr(root, "iter_dfs", lambda: ())():
        rows.append(
            {
                "tag_name": getattr(element, "tag_name", None),
                "backend_node_id": getattr(element, "backend_node_id", None),
                "node_id": getattr(element, "node_id", None),
                "parent_backend_node_id": getattr(element, "parent_backend_node_id", None),
                "node_type": getattr(element, "node_type", None),
                "is_text_node": getattr(element, "is_text_node", None),
                "bounds": {
                    "x": getattr(element, "x", None),
                    "y": getattr(element, "y", None),
                    "width": getattr(element, "width", None),
                    "height": getattr(element, "height", None),
                },
                "attributes": [
                    {
                        "name": getattr(attr, "name", None),
                        "value": getattr(attr, "value", None),
                    }
                    for attr in getattr(element, "attributes", ()) or ()
                ],
                "properties": [
                    {
                        "name": getattr(prop, "name", None),
                        "value": getattr(prop, "value", None),
                        "has_color": getattr(prop, "has_color", None),
                    }
                    for prop in getattr(element, "properties", ()) or ()
                ],
            }
        )
    return pformat(rows, sort_dicts=False, width=120)


# DEBUG TEMPORAL: imprime ColorScheme.colors en results.html para validar capture_original_state.
# Eliminar cuando assemble_results vuelva a consultar ColorScheme directamente.
def _debug_color_scheme_text(color_scheme: Any) -> str:
    if color_scheme is None:
        return ""

    colors = getattr(color_scheme, "get_colors", lambda: {})() or {}
    return pformat(
        {
            key: _debug_value(color)
            for key, color in colors.items()
        },
        sort_dicts=False,
        width=120,
    )


# DEBUG TEMPORAL: normaliza objetos de dominio para imprimirlos como texto plano.
# Eliminar cuando assemble_results vuelva a consultar Summary directamente.
def _debug_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            _debug_value(key): _debug_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_debug_value(item) for item in value]
    to_string = getattr(value, "to_string", None)
    if callable(to_string):
        try:
            return to_string(comma=True, alpha=True)
        except Exception:
            return str(value)
    return value


# DEBUG TEMPORAL: conserva datos legacy minimos para las secciones no migradas.
# Eliminar cuando results.html consuma modelos de dominio directamente.
def _fallback_template_payload(context: PipelineContext) -> dict[str, Any] | None:
    if context.error or not context.has(K.SESSION):
        return None

    session = context.get(K.SESSION)
    color_scheme = context.get(K.COLOR_SCHEME)
    session_dirname = session.session_dir.name
    html_candidates = session.find_by_suffix("before", ("html",))
    html_name = html_candidates[0].name if html_candidates else ""
    palette_rows = _palette_rows(color_scheme)
    summary = context.get(K.SUMMARY) if context.has(K.SUMMARY) else None
    before_assessment = (
        context.get(K.ENVIRONMENTAL_BEFORE_ASSESSMENT)
        if context.has(K.ENVIRONMENTAL_BEFORE_ASSESSMENT)
        else None
    )
    after_assessment = (
        context.get(K.ENVIRONMENTAL_AFTER_ASSESSMENT)
        if context.has(K.ENVIRONMENTAL_AFTER_ASSESSMENT)
        else None
    )
    environmental_savings = (
        context.get(K.ENVIRONMENTAL_SAVINGS)
        if context.has(K.ENVIRONMENTAL_SAVINGS)
        else None
    )
    snapshot_debug = context.get("derived.snapshot_debug", "")
    dom_tree_debug = _debug_dom_tree_text(context.get(K.DOM_TREE))
    color_scheme_debug = _debug_color_scheme_text(color_scheme)

    results = {
        "total_current": float(getattr(before_assessment, "current_a", 0.0) or 0.0),
        "carbon_footprint": float(getattr(before_assessment, "co2eq_per_use", 0.0) or 0.0),
        "energy_wh": float(getattr(before_assessment, "energy_wh", 0.0) or 0.0),
        "environmental_energy_wh": float(getattr(after_assessment, "energy_wh", 0.0) or 0.0),
        "environmental_co2eq_per_use": float(getattr(after_assessment, "co2eq_per_use", 0.0) or 0.0),
        "session_id": session.session_id,
        "session_dirname": session_dirname,
        "html_name": html_name,
        "heuristics": [],
        "debug": context.trace.to_dict() if context.trace else None,
        "debug_screenshots": {
            "before": "before.png",
            "after": "after.png",
        },
        "debug_summary_text": _debug_summary_text(summary),
        "recommendations": {"items": [], "summary": None},
        "download_url": "",
        "environmental_assessment": {
            "before": before_assessment.to_dict() if before_assessment is not None else {},
            "after": after_assessment.to_dict() if after_assessment is not None else {},
            "savings": environmental_savings.to_dict() if environmental_savings is not None else {},
        },
        "render_snapshot": {
            "node_count": len(list(context.get(K.DOM_TREE).iter_dfs())) if context.has(K.DOM_TREE) else 0,
            "palette_color_count": len(color_scheme.get_colors()) if color_scheme else 0,
        },
        "color_processing": {
            "palette_preview_location": "artifacts",
            "dominant_color_percentages": [],
            "named_color_breakdown": [],
            "core_palettes": {"achromatic_palette": {}, "chromatic_palettes": []},
            "color_usages": {},
        },
        "token_processing": {
            "token_count": 0,
            "foundation_token_count": 0,
            "semantic_token_count": 0,
            "component_token_count": 0,
            "failed_token_count": 0,
            "tokenized_element_count": 0,
            "tokenized_style_ref_count": 0,
            "tokenized_color_count": 0,
            "tokenized_palette_tone_count": 0,
        },
        "accessibility": {
            "contrast": {
                "issue_count": 0,
                "issues": [],
                "linked_issue_count": 0,
            }
        },
        "effect_colors": {
            "entry_count": 0,
            "entries": [],
            "properties": [],
        },
        "snapshot_debug": snapshot_debug,
        "dom_tree_debug": dom_tree_debug,
        "color_scheme_debug": color_scheme_debug,
        "view": {
            "initial_reduction": float(getattr(environmental_savings, "co2eq_per_use", 0.0) or 0.0),
            "dominant_rows": [],
            "dominant_color_count": 0,
            "top_three_percentage": 0,
            "palette_rows": palette_rows,
            "contrast_rows": [],
            "change_history_groups": _change_history_groups(summary),
        },
    }
    return {
        "results": results,
        "summary": summary,
    }


def _close_page_builder(context: PipelineContext) -> None:
    page_builder = context.get(K.PAGE_BUILDER)
    close = getattr(page_builder, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            pass
    context.delete(K.PAGE_BUILDER)


def run_pipeline(file) -> tuple[dict[str, Any] | None, str | None]:
    context = PipelineContext(trace=DebugTrace(enabled=True))
    try:
        try:
            context.trace.add_stage_event(PREPARE_PROJECT_SESSION_CONTRACT.name, "validate_requires")
            validate_requires(context, PREPARE_PROJECT_SESSION_CONTRACT)
            context = run_prepare_project_session_stage(context, file)
            if not context.error:
                context.trace.add_stage_event(PREPARE_PROJECT_SESSION_CONTRACT.name, "validate_produces")
                validate_produces(context, PREPARE_PROJECT_SESSION_CONTRACT)
        except PipelineContractError as exc:
            context.set_error(str(exc))
            context.trace.add_stage_event(
                PREPARE_PROJECT_SESSION_CONTRACT.name,
                "error",
                {"message": context.error},
            )
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            context.set_error(str(exc))
            context.trace.add_stage_event(
                PREPARE_PROJECT_SESSION_CONTRACT.name,
                "error",
                {"message": context.error},
            )

        for contract, stage_runner in _STAGES:
            if context.error:
                break
            try:
                context.trace.add_stage_event(contract.name, "validate_requires")
                validate_requires(context, contract)
                context = stage_runner(context)
                if context.error:
                    context.trace.add_stage_event(
                        contract.name,
                        "error",
                        {"message": context.error},
                    )
                    break
                context.trace.add_stage_event(contract.name, "validate_produces")
                validate_produces(context, contract)
            except PipelineContractError as exc:
                context.set_error(str(exc))
                context.trace.add_stage_event(
                    contract.name,
                    "error",
                    {"message": context.error},
                )
                break
            except Exception as exc:  # pragma: no cover - defensive runtime guard
                context.set_error(str(exc))
                context.trace.add_stage_event(
                    contract.name,
                    "error",
                    {"message": context.error},
                )
                break
    finally:
        if context.has(K.PAGE_BUILDER):
            _close_page_builder(context)
    return PipelineResult(payload=_fallback_template_payload(context), error=context.error).to_tuple()
