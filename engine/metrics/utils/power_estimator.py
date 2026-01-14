from typing import Iterable, Mapping

from engine.metrics.models.energy_model import EnergyModel


def estimate_power(
    color_data: Iterable[Mapping[str, object]],
    energy_model: EnergyModel,
) -> float:
    """Estimate power/current based on screenshot analyzer output."""
    return energy_model.calculate_power(color_data)
