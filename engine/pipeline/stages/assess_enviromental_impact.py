from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from engine.adapters.utils.pixel import build_histogram, image_to_array
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import Color
from engine.domain.models.environmental_assessment.assessment import (
    EnvironmentalAssessmentModel,
    EnvironmentalSavingsModel,
)
from engine.domain.models.environmental_assessment.carbon_footprint import (
    CarbonFootprintModel,
    assess_interface,
)
from engine.domain.models.environmental_assessment.energy_consumption import EnergyModel
from engine.domain.models.session import Session
from engine.domain.models.summary import Summary
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

_ENERGY_MODEL = EnergyModel.build_default()
_CARBON_MODEL = CarbonFootprintModel.build_default()


def _session_ready_for_environmental_assessment(session: Session) -> bool:
    return bool(session.session_id.strip())


def _summary_ready_for_environmental_assessment(summary: Summary) -> bool:
    overview = summary.overview("environmental_color_histogram")
    return overview is not None and isinstance(overview.data, dict)


def _summary_has_environmental_assessment(summary: Summary) -> bool:
    after_overview = summary.overview("environmental_color_histogram_after")
    return (
        _summary_ready_for_environmental_assessment(summary)
        and after_overview is not None
        and isinstance(after_overview.data, dict)
        and summary.environmental_review() is not None
    )


CONTRACT = StageContract(
    name="assess_enviromental_impact",
    requires=(
        context_value(
            K.SESSION,
            Session,
            validator=_session_ready_for_environmental_assessment,
        ),
        context_value(
            K.SUMMARY,
            Summary,
            validator=_summary_ready_for_environmental_assessment,
        ),
    ),
    produces=(
        context_value(
            K.SUMMARY,
            Summary,
            validator=_summary_has_environmental_assessment,
        ),
        context_value(K.ENVIRONMENTAL_BEFORE_ASSESSMENT, EnvironmentalAssessmentModel),
        context_value(K.ENVIRONMENTAL_AFTER_ASSESSMENT, EnvironmentalAssessmentModel),
        context_value(K.ENVIRONMENTAL_SAVINGS, EnvironmentalSavingsModel),
    ),
)


def _build_savings(
    before: EnvironmentalAssessmentModel,
    after: EnvironmentalAssessmentModel,
) -> EnvironmentalSavingsModel:
    savings: dict[str, float] = {}
    for key in ("current_a", "energy_wh", "co2eq_per_use"):
        before_value = float(getattr(before, key) or 0.0)
        after_value = float(getattr(after, key) or 0.0)
        delta = round(before_value - after_value, 6)
        savings[key] = delta
        savings[f"{key}_percent"] = round((delta / before_value) * 100, 4) if before_value else 0.0
    return EnvironmentalSavingsModel.build(savings)


def _overview_data(summary: Summary, overview_name: str) -> Any:
    overview = summary.overview(overview_name)
    return overview.data if overview is not None else {}


def _histogram_records(histogram: object) -> list[dict[str, object]]:
    if isinstance(histogram, Mapping):
        return [
            {
                "color": list(_rgb_channels(color_value)),
                "count": int(count),
            }
            for color_value, count in histogram.items()
        ]

    records: list[dict[str, object]] = []
    if not isinstance(histogram, Iterable) or isinstance(histogram, (str, bytes)):
        return records

    for item in histogram:
        if not isinstance(item, Mapping):
            continue
        try:
            color_value = item.get("color")
            count = int(item.get("count") or 0)
            records.append({"color": list(_rgb_channels(color_value)), "count": count})
        except Exception:
            continue
    return records


def _rgb_channels(color_value: object) -> tuple[int, int, int]:
    if not isinstance(color_value, (str, bytes)):
        try:
            red, green, blue = tuple(color_value)[:3]  # type: ignore[arg-type]
            return (
                max(0, min(255, round(float(red)))),
                max(0, min(255, round(float(green)))),
                max(0, min(255, round(float(blue)))),
            )
        except Exception:
            pass

    color = Color(str(color_value))
    red, green, blue = color.convert("srgb").coords(nans=False)
    return (
        max(0, min(255, round(float(red) * 255))),
        max(0, min(255, round(float(green) * 255))),
        max(0, min(255, round(float(blue) * 255))),
    )


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has(K.ENVIRONMENTAL_SAVINGS):
        return context

    session = context.get(K.SESSION)
    summary = context.get(K.SUMMARY)

    context.trace.add_stage_event(CONTRACT.name, "start")
    screenshot_path = session.get_path("after.png", "artifacts", "png")
    pixel_matrix = image_to_array(screenshot_path)
    environmental_histogram = build_histogram(pixel_matrix)
    summary.add_overview(
        "environmental_color_histogram_after",
        environmental_histogram,
    )

    before_assessment = EnvironmentalAssessmentModel.build(
        assess_interface(
            _histogram_records(_overview_data(summary, "environmental_color_histogram")),
            energy_model=_ENERGY_MODEL,
            carbon_model=_CARBON_MODEL,
            time_hours=1,
        )
    )
    after_assessment = EnvironmentalAssessmentModel.build(
        assess_interface(
            _histogram_records(_overview_data(summary, "environmental_color_histogram_after")),
            energy_model=_ENERGY_MODEL,
            carbon_model=_CARBON_MODEL,
            time_hours=1,
        )
    )
    savings = _build_savings(before_assessment, after_assessment)

    summary.add_environmental_review(
        energy_consumption=after_assessment.energy_wh,
        carbon_footprint=after_assessment.co2eq_per_use,
        carbon_footprint_reduction=savings.co2eq_per_use,
    )
    context.set(K.SUMMARY, summary)
    context.set(K.ENVIRONMENTAL_BEFORE_ASSESSMENT, before_assessment)
    context.set(K.ENVIRONMENTAL_AFTER_ASSESSMENT, after_assessment)
    context.set(K.ENVIRONMENTAL_SAVINGS, savings)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "before_co2eq_per_use": before_assessment.co2eq_per_use,
            "after_co2eq_per_use": after_assessment.co2eq_per_use,
            "co2eq_per_use_savings": savings.co2eq_per_use,
        },
    )
    return context
