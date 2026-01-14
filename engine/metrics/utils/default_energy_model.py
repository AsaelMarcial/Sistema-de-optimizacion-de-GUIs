from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from engine.metrics.models.energy_model import EnergyModel


def build_default_energy_model() -> EnergyModel:
    module_path = Path(__file__).resolve().parents[2] / "energy-model" / "energy_model.py"
    spec = spec_from_file_location("energy_model_defaults", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"No se pudo cargar el modelo de energía desde {module_path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_default_energy_model()
