from __future__ import annotations

from engine.domain.models.environmental_assessment.carbon_footprint import (
    CarbonFootprintModel,
    assess_interface,
)
from engine.domain.models.environmental_assessment.assessment import EnvironmentalAssessmentModel
from engine.domain.models.environmental_assessment.energy_consumption import EnergyModel
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value

_ENERGY_MODEL = EnergyModel.build_default()
_CARBON_MODEL = CarbonFootprintModel.build_default()

CONTRACT = StageContract(
    name="assess_original_environmental_impact",
    requires=(
        context_value(K.ENVIRONMENTAL_BEFORE_COLOR_HISTOGRAM, list),
    ),
    produces=(
        context_value(K.ENVIRONMENTAL_BEFORE_ASSESSMENT, EnvironmentalAssessmentModel),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has(K.ENVIRONMENTAL_BEFORE_ASSESSMENT):
        return context

    context.trace.add_stage_event(CONTRACT.name, "start")
    assessment = EnvironmentalAssessmentModel.build(
        assess_interface(
            context.get(K.ENVIRONMENTAL_BEFORE_COLOR_HISTOGRAM, []),
            energy_model=_ENERGY_MODEL,
            carbon_model=_CARBON_MODEL,
            time_hours=1,
        )
    )
    context.set(K.ENVIRONMENTAL_BEFORE_ASSESSMENT, assessment)
    context.trace.add_step(
        "assessment.original",
        {
            "total_current": assessment.current_a,
            "energy_wh": assessment.energy_wh,
            "co2eq_per_use": assessment.co2eq_per_use,
        },
    )
    context.trace.add_stage_event(CONTRACT.name, "complete", assessment.to_dict())
    return context
