from typing import Dict, Optional

from engine.environmental_assessment.models.carbon_footprint_calculator import CarbonFootprintCalculator
from engine.environmental_assessment.models.energy_model import EnergyModel
from engine.environmental_assessment.utils.environmental_utils import estimate_interface_current


def run_environmental_assessment(
    color_data,
    energy_model: EnergyModel,
    *,
    time_hours: float = 1,
    user_count: int = 100,
    usage_hours: int = 24,
    calculator: Optional[CarbonFootprintCalculator] = None,
) -> Dict[str, float]:
    current_a = estimate_interface_current(color_data, energy_model)
    calculator = calculator or CarbonFootprintCalculator()
    assessment = calculator.calculate(
        current_a=current_a,
        time_hours=time_hours,
        user_count=user_count,
        usage_hours=usage_hours,
    )
    assessment["current_a"] = current_a
    return assessment
