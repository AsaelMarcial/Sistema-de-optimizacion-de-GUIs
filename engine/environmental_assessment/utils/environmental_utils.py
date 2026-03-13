from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Iterable, Mapping

from engine.environmental_assessment.models.energy_model import EnergyModel


def build_default_energy_model() -> EnergyModel:
    module_path = Path(__file__).resolve().parents[2] / "energy-model" / "energy_model.py"
    spec = spec_from_file_location("energy_model_defaults", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar el modelo de energía desde {module_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_default_energy_model()


def estimate_interface_current(color_data: Iterable[Mapping[str, object]], energy_model: EnergyModel) -> float:
    return energy_model.calculate_power(color_data)
