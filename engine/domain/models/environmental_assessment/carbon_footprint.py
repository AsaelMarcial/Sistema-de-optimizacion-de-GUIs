from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import ClassVar, Iterable, Mapping, Self

from engine.domain.models.environmental_assessment.energy_consumption import (
    EnergyModel,
    estimate_current,
)


DEFAULT_VOLTAGE = 3.7
DEFAULT_EMISSION_FACTOR = 475.0
DEFAULT_HARDWARE_EMISSIONS = 0.0


@dataclass(frozen=True, slots=True)
class CarbonFootprintModel:
    """
    Immutable carbon assessment profile used to translate current draw into SCI-related metrics.
    """

    DEFAULT_VOLTAGE: ClassVar[float] = DEFAULT_VOLTAGE
    DEFAULT_EMISSION_FACTOR: ClassVar[float] = DEFAULT_EMISSION_FACTOR
    DEFAULT_HARDWARE_EMISSIONS: ClassVar[float] = DEFAULT_HARDWARE_EMISSIONS

    voltage: float
    emission_factor: float
    hardware_emissions: float

    @classmethod
    def build(
        cls,
        *,
        voltage: float,
        emission_factor: float,
        hardware_emissions: float = DEFAULT_HARDWARE_EMISSIONS,
    ) -> Self:
        return cls(
            voltage=float(voltage),
            emission_factor=float(emission_factor),
            hardware_emissions=float(hardware_emissions),
        )

    @classmethod
    def build_default(cls) -> Self:
        return cls.build(
            voltage=cls.DEFAULT_VOLTAGE,
            emission_factor=cls.DEFAULT_EMISSION_FACTOR,
            hardware_emissions=cls.DEFAULT_HARDWARE_EMISSIONS,
        )

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def calculate(
    *,
    current_a: float,
    time_hours: float,
    carbon_model: CarbonFootprintModel,
    r: float = 1,
    user_count: int = 100,
    usage_hours: int = 24,
) -> dict[str, float | int]:
    energy_wh = float(current_a) * carbon_model.voltage * float(time_hours)
    energy_kwh = energy_wh / 1000
    co2eq_per_use = energy_kwh * carbon_model.emission_factor
    sci_score = (co2eq_per_use + carbon_model.hardware_emissions) / float(r)
    co2eq_total = co2eq_per_use * int(user_count) * int(usage_hours)

    return {
        "energy_wh": energy_wh,
        "energy_kwh": energy_kwh,
        "co2eq_per_use": co2eq_per_use,
        "co2eq_total": co2eq_total,
        "sci_score": sci_score,
        "emission_factor": carbon_model.emission_factor,
        "user_count": int(user_count),
        "usage_hours": int(usage_hours),
        "ahorro_potencial": 0,
    }


def assess_interface(
    pixel_data: Iterable[Mapping[str, object]],
    *,
    energy_model: EnergyModel,
    carbon_model: CarbonFootprintModel,
    time_hours: float = 1,
    user_count: int = 100,
    usage_hours: int = 24,
) -> dict[str, float | int]:
    current_a = estimate_current(pixel_data, energy_model)
    assessment = calculate(
        current_a=current_a,
        time_hours=time_hours,
        carbon_model=carbon_model,
        user_count=user_count,
        usage_hours=usage_hours,
    )
    assessment["current_a"] = current_a
    return assessment
