from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Mapping

from engine.domain.models.style import PropertyUsageModel
from engine.domain.utils.colors import color_to_hex, color_to_rgb_tuple, display_color, hct_coords


@dataclass(frozen=True, slots=True)
class PixelColorRecord:
    color: tuple[int, int, int]
    count: int
    color_id: str | None = None
    percentage: float | None = None
    alpha: float | None = None
    source: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "PixelColorRecord":
        color = tuple(int(channel) for channel in payload.get("color", ()))  # type: ignore[arg-type]
        if len(color) != 3:
            raise ValueError(f"Pixel color invalido: {payload!r}")
        return cls(
            color=color,  # type: ignore[arg-type]
            count=int(payload.get("count", 0)),
            color_id=str(payload["color_id"]) if payload.get("color_id") is not None else None,
            percentage=(
                round(float(payload["percentage"]), 4)
                if payload.get("percentage") is not None
                else None
            ),
            alpha=float(payload["alpha"]) if payload.get("alpha") is not None else None,
            source=str(payload["source"]) if payload.get("source") is not None else None,
            metadata=dict(payload.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "color": list(self.color),
            "count": self.count,
        }
        if self.color_id is not None:
            payload["color_id"] = self.color_id
        if self.percentage is not None:
            payload["percentage"] = self.percentage
        if self.alpha is not None:
            payload["alpha"] = round(self.alpha, 4)
        if self.source is not None:
            payload["source"] = self.source
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True, slots=True)
class PixelColorFrequency:
    color: tuple[int, int, int]
    count: int

    def to_record(self) -> PixelColorRecord:
        return PixelColorRecord(color=self.color, count=self.count)

    def to_dict(self) -> dict[str, Any]:
        return self.to_record().to_dict()


@dataclass(frozen=True, slots=True)
class PixelColorStatistic:
    color_id: str
    color: tuple[int, int, int]
    count: int
    percentage: float

    def to_record(self) -> PixelColorRecord:
        return PixelColorRecord(
            color=self.color,
            count=self.count,
            color_id=self.color_id,
            percentage=round(self.percentage, 4),
        )

    def to_dict(self) -> dict[str, Any]:
        return self.to_record().to_dict()


@dataclass(frozen=True, slots=True)
class SnapshotColorEvidence:
    color_id: str
    rgb: tuple[int, int, int]
    alpha: float
    hct: tuple[float, float, float]
    family_type: str
    usage_count: int
    foreground_count: int
    background_count: int
    other_count: int
    foreground_color_usages: tuple[PropertyUsageModel, ...] = field(default_factory=tuple)
    background_color_usages: tuple[PropertyUsageModel, ...] = field(default_factory=tuple)
    other_usages: tuple[PropertyUsageModel, ...] = field(default_factory=tuple)
    confirmed_pixel_count: int = 0
    nearest_web_color: str | None = None
    nearest_web_color_distance: float | None = None
    confirmation_status: str = "semantic_only"
    mapped_palette_id: str | None = None
    mapped_tone: int | None = None
    mapped_tone_rgb: tuple[int, int, int] | None = None
    mapped_tone_distance: float | None = None

    def __iter__(self) -> Iterator[PropertyUsageModel]:
        yield from self.foreground_color_usages
        yield from self.background_color_usages
        yield from self.other_usages

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["rgb"] = list(self.rgb)
        payload["hct"] = list(self.hct)
        payload["foreground_color_usages"] = [
            item.to_dict() for item in self.foreground_color_usages
        ]
        payload["background_color_usages"] = [
            item.to_dict() for item in self.background_color_usages
        ]
        payload["other_usages"] = [item.to_dict() for item in self.other_usages]
        if self.mapped_tone_rgb is not None:
            payload["mapped_tone_rgb"] = list(self.mapped_tone_rgb)
        return payload


@dataclass(frozen=True, slots=True)
class ToneStopModel:
    tone: int
    hex_value: str
    rgb: tuple[int, int, int]
    hct: tuple[float, float, float]

    @classmethod
    def from_color(cls, tone: int, color_value: Any) -> "ToneStopModel":
        normalized = display_color(color_value)
        return cls(
            tone=tone,
            hex_value=color_to_hex(normalized),
            rgb=color_to_rgb_tuple(normalized),
            hct=hct_coords(normalized),  # type: ignore[arg-type]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tone": self.tone,
            "hex_value": self.hex_value,
            "rgb": list(self.rgb),
            "hct": list(self.hct),
        }
