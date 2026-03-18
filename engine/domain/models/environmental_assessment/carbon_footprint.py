from __future__ import annotations


class CarbonFootprintCalculator:
    """Calculates energy consumption and SCI score using Green Software Foundation methodology."""

    def __init__(
        self,
        voltage: float = 3.7,
        emission_factor: float = 475,
        hardware_emissions: float = 0,
    ) -> None:
        self.voltage = voltage
        self.emission_factor = emission_factor
        self.hardware_emissions = hardware_emissions

    @classmethod
    def build_default(cls) -> "CarbonFootprintCalculator":
        return cls()

    def calculate(
        self,
        current_a: float,
        time_hours: float,
        r: float = 1,
        user_count: int = 100,
        usage_hours: int = 24,
    ) -> dict[str, float | int]:
        energy_wh = current_a * self.voltage * time_hours
        energy_kwh = energy_wh / 1000
        co2eq_per_use = energy_kwh * self.emission_factor
        sci_score = (co2eq_per_use + self.hardware_emissions) / r
        co2eq_total = co2eq_per_use * user_count * usage_hours

        return {
            "energy_wh": energy_wh,
            "energy_kwh": energy_kwh,
            "co2eq_per_use": co2eq_per_use,
            "co2eq_total": co2eq_total,
            "sci_score": sci_score,
            "emission_factor": self.emission_factor,
            "user_count": user_count,
            "usage_hours": usage_hours,
            "ahorro_potencial": 0,
        }
