from typing import Dict


def estimate_energy_consumption(
    current_a: float,
    time_hours: float,
    voltage: float = 3.7,
) -> Dict[str, float]:
    energy_wh = current_a * voltage * time_hours
    energy_kwh = energy_wh / 1000
    return {
        "energy_wh": energy_wh,
        "energy_kwh": energy_kwh,
    }
