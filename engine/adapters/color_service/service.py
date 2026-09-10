from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from coloraide.everything import ColorAll

from .strategies.contrast import (
    ColorAideContrastStrategy,
    ContrastOperationsMixin,
    ContrastStrategy,
    LegacyRGBHeuristicStrategy,
    RGBHeuristicStrategy,
)
from .strategies.distance import DeltaEDistanceStrategy, DistanceOperationsMixin, DistanceStrategy
from .strategies.format import (
    ColorFormatStrategy,
    FormatOperationsMixin,
)
from .strategies.gamut import GamutStrategy
from .strategies.match import (
    HEX_COLOR_RE,
    RGB_INPUT_RE,
    ColorMatchStrategy,
    MatchOperationsMixin,
)
from .strategies.palette import HCTPaletteStrategy, PaletteOperationsMixin, PaletteStrategy

RGBColor: TypeAlias = tuple[int, int, int]
RGBAColor: TypeAlias = tuple[int, int, int, float]
HCTColor: TypeAlias = tuple[float, float, float]
ColorLike: TypeAlias = ColorAll | str | Sequence[int | float]
ColorTextRange: TypeAlias = tuple[int, int, str]
FormatName: TypeAlias = Literal["hex", "rgb", "rgba", "css", "hct"]


@dataclass
class StrategyRegistry(
    FormatOperationsMixin,
    MatchOperationsMixin,
    PaletteOperationsMixin,
    DistanceOperationsMixin,
    ContrastOperationsMixin,
):
    distance: dict[str, DistanceStrategy] = field(default_factory=dict)
    contrast: dict[str, ContrastStrategy] = field(default_factory=dict)
    gamut: dict[str, GamutStrategy] = field(default_factory=dict)
    formatter: dict[str, ColorFormatStrategy] = field(default_factory=dict)
    palette: dict[str, PaletteStrategy] = field(default_factory=dict)
    match: dict[str, ColorMatchStrategy] = field(default_factory=dict)
    rgb_heuristic: dict[str, RGBHeuristicStrategy] = field(default_factory=dict)
    gamut_strategy: str = "hct-chroma"
    distance_strategy: str = "delta-e"
    distance_method: str = "2000"
    contrast_strategy: str = "wcag21"
    palette_strategy: str = "hct"
    palette_chroma_override: float | None = None
    match_strategy: str = "css"
    rgb_match_strategy: str = "css-rgb"
    hex_match_strategy: str = "css-hex"
    heuristic_strategy: str = "legacy-rgb"

    def register_distance(self, strategy: DistanceStrategy) -> None:
        self.distance[strategy.name.lower()] = strategy

    def register_contrast(self, strategy: ContrastStrategy) -> None:
        self.contrast[strategy.name.lower()] = strategy

    def register_gamut(self, strategy: GamutStrategy) -> None:
        self.gamut[strategy.name.lower()] = strategy

    def register_formatter(self, strategy: ColorFormatStrategy) -> None:
        self.formatter[strategy.name.lower()] = strategy

    def register_palette(self, strategy: PaletteStrategy) -> None:
        self.palette[strategy.name.lower()] = strategy

    def register_match(self, strategy: ColorMatchStrategy) -> None:
        self.match[strategy.name.lower()] = strategy

    def register_rgb_heuristic(self, strategy: RGBHeuristicStrategy) -> None:
        self.rgb_heuristic[strategy.name.lower()] = strategy

    def get_distance(self, name: str) -> DistanceStrategy:
        return self.distance[name.lower()]

    def get_contrast(self, name: str) -> ContrastStrategy:
        return self.contrast[name.lower()]

    def get_gamut(self, name: str) -> GamutStrategy:
        return self.gamut[name.lower()]

    def get_formatter(self, name: FormatName) -> ColorFormatStrategy:
        return self.formatter[name.lower()]

    def get_palette(self, name: str) -> PaletteStrategy:
        return self.palette[name.lower()]

    def get_match(self, name: str) -> ColorMatchStrategy:
        return self.match[name.lower()]

    def get_rgb_heuristic(self, name: str) -> RGBHeuristicStrategy:
        return self.rgb_heuristic[name.lower()]


def build_default_strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register_distance(DeltaEDistanceStrategy())
    registry.register_contrast(ColorAideContrastStrategy(name="wcag21", method="wcag21"))
    registry.register_gamut(GamutStrategy(name="hct-chroma", method="hct-chroma", pspace="hct"))
    registry.register_formatter(ColorFormatStrategy("hex"))
    registry.register_formatter(ColorFormatStrategy("rgb"))
    registry.register_formatter(ColorFormatStrategy("rgba"))
    registry.register_formatter(ColorFormatStrategy("css"))
    registry.register_formatter(ColorFormatStrategy("hct"))
    registry.register_palette(HCTPaletteStrategy())
    registry.register_match(ColorMatchStrategy())
    registry.register_match(ColorMatchStrategy(name="css-rgb", pattern=RGB_INPUT_RE))
    registry.register_match(ColorMatchStrategy(name="css-hex", pattern=HEX_COLOR_RE))
    registry.register_rgb_heuristic(LegacyRGBHeuristicStrategy())
    return registry


color_registry = build_default_strategy_registry()
