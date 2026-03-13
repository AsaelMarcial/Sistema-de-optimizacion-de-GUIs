from typing import Iterable, Mapping

from engine.environmental_assessment.models.energy_model import EnergyModel

DEFAULT_COEFFICIENTS_R = [
    1.804551146759771e-07,
    -3.0220347704227896e-07,
    1.4154405902803595e-07,
]
DEFAULT_COEFFICIENTS_G = [
    9.412383738420182e-08,
    -1.5781520809511624e-07,
    7.546610037732226e-08,
]
DEFAULT_COEFFICIENTS_B = [
    1.3946409007268839e-08,
    -2.4495186160412765e-08,
    1.598790315272048e-08,
]
DEFAULT_CONSTANT_C = 0.120833


def build_default_energy_model() -> EnergyModel:
    return EnergyModel(
        DEFAULT_COEFFICIENTS_R,
        DEFAULT_COEFFICIENTS_G,
        DEFAULT_COEFFICIENTS_B,
        DEFAULT_CONSTANT_C,
    )


def estimate_interface_current(color_data: Iterable[Mapping[str, object]], energy_model: EnergyModel) -> float:
    return energy_model.calculate_power(color_data)
