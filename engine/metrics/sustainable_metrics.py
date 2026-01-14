from typing import Dict, Optional

from engine.metrics.models.energy_model import EnergyModel
from engine.metrics.utils.energy_estimator import estimate_energy_consumption
from engine.metrics.utils.power_estimator import estimate_power


class CarbonFootprintCalculator:
    """
    Calculates energy consumption and carbon emissions using Green Software Foundation methodology.
    """

    def __init__(self, voltage: float = 3.7, emission_factor: float = 475, hardware_emissions: float = 0):
        self.voltage = voltage
        self.emission_factor = emission_factor
        self.hardware_emissions = hardware_emissions

    def estimate(
        self,
        current_a: float,
        time_hours: float,
        user_count: int = 100,
        usage_hours: int = 24,
    ) -> Dict[str, float]:
        energy = estimate_energy_consumption(current_a, time_hours, self.voltage)
        co2eq_per_use = energy["energy_kwh"] * self.emission_factor
        co2eq_total = co2eq_per_use * user_count * usage_hours

        return {
            "energy_wh": energy["energy_wh"],
            "energy_kwh": energy["energy_kwh"],
            "co2eq_per_use": co2eq_per_use,
            "co2eq_total": co2eq_total,
            "emission_factor": self.emission_factor,
            "user_count": user_count,
            "usage_hours": usage_hours,
            "hardware_emissions": self.hardware_emissions,
            "ahorro_potencial": 0,
        }


def estimate_sustainable_metrics(
    color_data,
    energy_model: EnergyModel,
    *,
    time_hours: float = 1,
    user_count: int = 100,
    usage_hours: int = 24,
    calculator: Optional[CarbonFootprintCalculator] = None,
) -> Dict[str, float]:
    current_a = estimate_power(color_data, energy_model)
    calculator = calculator or CarbonFootprintCalculator()
    footprint = calculator.estimate(
        current_a=current_a,
        time_hours=time_hours,
        user_count=user_count,
        usage_hours=usage_hours,
    )
    footprint["current_a"] = current_a
    return footprint
