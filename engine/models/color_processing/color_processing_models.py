from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class PixelColorFrequency:
    color: tuple[int, int, int]
    count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "color": list(self.color),
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class PixelColorStatistic:
    color_id: str
    color: tuple[int, int, int]
    count: int
    percentage: float

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["color"] = list(self.color)
        return payload


@dataclass(frozen=True, slots=True)
class MaterialQuantizationAssessment:
    recommended: bool
    summary: str
    resize_before_quantization: bool
    recommended_size: tuple[int, int]
    recommended_quantizer: str
    recommended_max_colors: int
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
