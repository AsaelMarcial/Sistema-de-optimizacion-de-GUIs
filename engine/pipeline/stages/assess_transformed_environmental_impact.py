from __future__ import annotations

from pathlib import Path

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.utils.pixel import build_color_histograms
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
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value

_ENERGY_MODEL = EnergyModel.build_default()
_CARBON_MODEL = CarbonFootprintModel.build_default()


def _session_ready_for_environmental_assessment(session: Session) -> bool:
    return bool(session.session_id.strip())

CONTRACT = StageContract(
    name="assess_transformed_environmental_impact",
    requires=(
        context_value(K.PAGE_BUILDER, PageBuilder),
        context_value(
            K.TRANSFORMATION_OUTPUT_HTML_PATH,
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            K.SESSION,
            Session,
            validator=_session_ready_for_environmental_assessment,
        ),
        context_value(K.ENVIRONMENTAL_BEFORE_ASSESSMENT, EnvironmentalAssessmentModel),
    ),
    produces=(
        context_value(K.ENVIRONMENTAL_AFTER_COLOR_HISTOGRAM, list),
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


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    session = context.get(K.SESSION)
    transformed_html_path = Path(context.get(K.TRANSFORMATION_OUTPUT_HTML_PATH)).resolve()
    screenshot_path = session.get_path("after.png", "artifacts", "png")
    context.trace.add_stage_event(
        CONTRACT.name,
        "start",
        {
            "base_path": str(transformed_html_path.parent),
            "output_image": str(screenshot_path),
        },
    )
    page_builder = context.get(K.PAGE_BUILDER)
    page_builder.load_file(transformed_html_path)
    screenshot_output_path = page_builder.capture_fullpage_screenshot(
        output_path=screenshot_path,
    )
    color_histograms = build_color_histograms(screenshot_output_path or screenshot_path)
    color_histogram = color_histograms["environmental"]
    context.set(K.ENVIRONMENTAL_AFTER_COLOR_HISTOGRAM, color_histogram)
    context.trace.add_step(
        "environmental_prototype.render_done",
        {
            "screenshot_path": str(screenshot_output_path or screenshot_path),
        },
    )
    context.trace.add_step(
        "environmental_prototype.colors_classified",
        {"distinct_colors": len(color_histogram)},
    )

    after_assessment = EnvironmentalAssessmentModel.build(
        assess_interface(
            color_histogram,
            energy_model=_ENERGY_MODEL,
            carbon_model=_CARBON_MODEL,
            time_hours=1,
        )
    )
    before_assessment = context.get(K.ENVIRONMENTAL_BEFORE_ASSESSMENT)
    savings = _build_savings(before_assessment, after_assessment)
    context.set(K.ENVIRONMENTAL_AFTER_ASSESSMENT, after_assessment)
    context.set(K.ENVIRONMENTAL_SAVINGS, savings)
    context.trace.add_step(
        "assessment.environmental",
        {
            "environmental_current": after_assessment.current_a,
            "environmental_energy_wh": after_assessment.energy_wh,
            "environmental_co2eq_per_use": after_assessment.co2eq_per_use,
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "distinct_colors": len(color_histogram),
            "co2eq_per_use_savings": savings.co2eq_per_use,
        },
    )
    return context
