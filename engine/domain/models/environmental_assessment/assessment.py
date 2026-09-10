from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Self


@dataclass(frozen=True, slots=True)
class EnvironmentalAssessmentModel:
    current_a: float
    energy_wh: float
    co2eq_per_use: float
    extras: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        extras = {
            str(key): value
            for key, value in dict(payload).items()
            if key not in {"current_a", "energy_wh", "co2eq_per_use"}
        }
        return cls(
            current_a=float(payload.get("current_a") or 0.0),
            energy_wh=float(payload.get("energy_wh") or 0.0),
            co2eq_per_use=float(payload.get("co2eq_per_use") or 0.0),
            extras=extras,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "current_a": round(self.current_a, 6),
            "energy_wh": round(self.energy_wh, 6),
            "co2eq_per_use": round(self.co2eq_per_use, 6),
        }
        payload.update(dict(self.extras))
        return payload


@dataclass(frozen=True, slots=True)
class EnvironmentalSavingsModel:
    current_a: float
    current_a_percent: float
    energy_wh: float
    energy_wh_percent: float
    co2eq_per_use: float
    co2eq_per_use_percent: float

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            current_a=float(payload.get("current_a") or 0.0),
            current_a_percent=float(payload.get("current_a_percent") or 0.0),
            energy_wh=float(payload.get("energy_wh") or 0.0),
            energy_wh_percent=float(payload.get("energy_wh_percent") or 0.0),
            co2eq_per_use=float(payload.get("co2eq_per_use") or 0.0),
            co2eq_per_use_percent=float(payload.get("co2eq_per_use_percent") or 0.0),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "current_a": round(self.current_a, 6),
            "current_a_percent": round(self.current_a_percent, 4),
            "energy_wh": round(self.energy_wh, 6),
            "energy_wh_percent": round(self.energy_wh_percent, 4),
            "co2eq_per_use": round(self.co2eq_per_use, 6),
            "co2eq_per_use_percent": round(self.co2eq_per_use_percent, 4),
        }
