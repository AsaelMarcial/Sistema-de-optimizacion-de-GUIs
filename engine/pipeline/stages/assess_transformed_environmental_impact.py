from __future__ import annotations

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
from engine.pipeline.stage_contract import StageContract, context_value

_ENERGY_MODEL = EnergyModel.build_default()
_CARBON_MODEL = CarbonFootprintModel.build_default()


def _session_ready_for_environmental_assessment(session: Session) -> bool:
    return (
        bool(session.session_id.strip())
        and bool(session.output_base_path.strip())
        and bool(session.transformed_screenshot_path.strip())
    )

CONTRACT = StageContract(
    name="assess_transformed_environmental_impact",
    requires=(
        context_value("session.page_builder", PageBuilder),
        context_value(
            "transformation.output.html.content",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session",
            Session,
            validator=_session_ready_for_environmental_assessment,
        ),
        context_value("environmental.before.assessment", EnvironmentalAssessmentModel),
    ),
    produces=(
        context_value("environmental.after.color_histogram", list),
        context_value("environmental.after.assessment", EnvironmentalAssessmentModel),
        context_value("environmental.savings", EnvironmentalSavingsModel),
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

    session = context.get("session")
    output_base_path = session.output_base_path
    screenshot_path = session.transformed_screenshot_path
    context.trace.add_stage_event(
        CONTRACT.name,
        "start",
        {
            "base_path": output_base_path,
            "output_image": screenshot_path,
        },
    )
    page_builder = context.get("session.page_builder")
    page_builder.load(
        context.get("transformation.output.html.content", ""),
        output_base_path,
    )
    screenshot_output_path = page_builder.capture_full_page_screenshot(
        artifacts_dir=session.artifacts_dir,
        filename=session.TRANSFORMED_SCREENSHOT_NAME,
    )
    color_histograms = build_color_histograms(screenshot_output_path or screenshot_path)
    color_histogram = color_histograms["environmental"]
    context.set("environmental.after.color_histogram", color_histogram)
    context.trace.add_step(
        "environmental_prototype.render_done",
        {
            "screenshot_path": screenshot_output_path or screenshot_path,
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
    before_assessment = context.get("environmental.before.assessment")
    savings = _build_savings(before_assessment, after_assessment)
    context.set("environmental.after.assessment", after_assessment)
    context.set("environmental.savings", savings)
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
