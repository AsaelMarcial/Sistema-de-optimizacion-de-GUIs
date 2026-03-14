from __future__ import annotations

from engine.models.environmental_assessment.carbon_footprint_calculator import (
    CarbonFootprintCalculator,
)
from engine.models.pipeline_context import PipelineContext
from engine.services.environmental_assessment.assessment_service import run_environmental_assessment
from engine.services.environmental_assessment.energy_profile_service import (
    build_default_energy_model,
)

_ENERGY_MODEL = build_default_energy_model()
_CALCULATOR = CarbonFootprintCalculator()


def _assess(context: PipelineContext, *, transformed: bool) -> None:
    artifacts = context.environmental_artifacts if transformed else context.original_artifacts
    assessment = run_environmental_assessment(
        artifacts.color_frequencies or [],
        _ENERGY_MODEL,
        time_hours=1,
        calculator=_CALCULATOR,
    )
    if transformed:
        context.environmental_assessment = assessment
        context.trace.add_step(
            "assessment.environmental",
            {
                "environmental_current": assessment["current_a"],
                "environmental_energy_wh": assessment.get("energy_wh"),
                "environmental_co2eq_per_use": assessment.get("co2eq_per_use"),
            },
        )
        return

    context.footprint = assessment
    context.trace.add_step(
        "assessment.original",
        {
            "total_current": assessment["current_a"],
            "energy_wh": assessment.get("energy_wh"),
            "co2eq_per_use": assessment.get("co2eq_per_use"),
        },
    )


def run_environmental_assessment_stage(context: PipelineContext) -> None:
    if context.error:
        return

    if context.original_artifacts is not None and context.footprint is None:
        _assess(context, transformed=False)
        return

    if context.environmental_artifacts is not None and context.environmental_assessment is None:
        _assess(context, transformed=True)
