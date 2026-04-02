from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol, cast

from coloraide.everything import ColorAll

RGBColor = tuple[int, int, int]

if TYPE_CHECKING:
    from ..service import ColorLike


def _as_rgb_color(value: list[int] | tuple[int, int, int]) -> RGBColor:
    """Normalize a mutable RGB buffer into a fixed RGBColor tuple."""
    if len(value) != 3:
        raise ValueError(f"RGB invalido: {value!r}")
    return int(value[0]), int(value[1]), int(value[2])


class ContrastStrategy(Protocol):
    @property
    def name(self) -> str:
        ...

    def contrast(self, foreground: ColorAll, background: ColorAll) -> float:
        ...


class RGBHeuristicStrategy(Protocol):
    @property
    def name(self) -> str:
        ...

    def is_light(self, rgb: RGBColor) -> bool:
        ...

    def luminance(self, rgb: RGBColor) -> float:
        ...

    def brighten(
        self,
        rgb: RGBColor,
        *,
        target_contrast: float,
        background_rgb: RGBColor,
        contrast_fn: Callable[[RGBColor, RGBColor], float],
    ) -> RGBColor:
        ...


@dataclass(frozen=True)
class ColorAideContrastStrategy:
    """Contrast strategy backed by ColorAide."""

    name: str
    method: str

    def contrast(self, foreground: ColorAll, background: ColorAll) -> float:
        """Return the configured ColorAide contrast metric."""
        return float(foreground.contrast(background, method=self.method))


@dataclass(frozen=True)
class LegacyRGBHeuristicStrategy:
    """Legacy RGB heuristic operations used by transformation routines."""

    name: str = "legacy-rgb"
    brightness_threshold: float = 180.0
    step: int = 10
    max_attempts: int = 25

    def is_light(self, rgb: RGBColor) -> bool:
        """Estimate whether an RGB color should be treated as light."""
        red, green, blue = rgb
        brightness = (red * 299 + green * 587 + blue * 114) / 1000
        return brightness > self.brightness_threshold

    def luminance(self, rgb: RGBColor) -> float:
        """Return the heuristic luminance used by legacy transformations."""
        red, green, blue = [channel / 255.0 for channel in rgb]
        return 0.2126 * (red**3) + 0.7152 * (green**3) + 0.0722 * (blue**3)

    def brighten(
        self,
        rgb: RGBColor,
        *,
        target_contrast: float,
        background_rgb: RGBColor,
        contrast_fn: Callable[[RGBColor, RGBColor], float],
    ) -> RGBColor:
        """Adjust an RGB color until it reaches the requested contrast."""
        new_rgb = [int(channel) for channel in rgb]
        attempts = 0
        current_rgb = _as_rgb_color(new_rgb)

        while contrast_fn(current_rgb, background_rgb) < target_contrast and attempts < self.max_attempts:
            if self.luminance(current_rgb) > self.luminance(background_rgb):
                new_rgb = [max(0, channel - self.step) for channel in new_rgb]
            else:
                new_rgb = [min(255, channel + self.step) for channel in new_rgb]
            attempts += 1
            current_rgb = _as_rgb_color(new_rgb)

        return current_rgb


class _ContrastRegistryProtocol(Protocol):
    """Capabilities required by contrast operations."""

    contrast_strategy: str
    heuristic_strategy: str

    def get_contrast(self, name: str) -> ContrastStrategy:
        ...

    def parse_color(self, value: ColorLike) -> ColorAll:
        ...

    def get_rgb_heuristic(self, name: str) -> RGBHeuristicStrategy:
        ...


class ContrastOperationsMixin:
    """Contrast and RGB heuristic operations expected by the registry."""

    def contrast_ratio(
        self,
        foreground: ColorLike,
        background: ColorLike,
        *,
        strategy_name: str | None = None,
    ) -> float:
        """Calculate perceptual contrast between two colors."""
        registry = cast(_ContrastRegistryProtocol, self)
        strategy = registry.get_contrast(strategy_name or registry.contrast_strategy)
        return strategy.contrast(registry.parse_color(foreground), registry.parse_color(background))

    def composite_over(self, foreground: ColorLike, background: ColorLike) -> ColorAll:
        """Alpha-composite a foreground color over a background color."""
        registry = cast(_ContrastRegistryProtocol, self)
        fg = registry.parse_color(foreground).convert("srgb")
        bg = registry.parse_color(background).convert("srgb")

        fg_red, fg_green, fg_blue = fg.coords()
        bg_red, bg_green, bg_blue = bg.coords()
        fg_alpha = float(fg.alpha())
        bg_alpha = float(bg.alpha())

        out_alpha = fg_alpha + (bg_alpha * (1.0 - fg_alpha))
        if out_alpha <= 0:
            return ColorAll("srgb", [0.0, 0.0, 0.0], alpha=0.0)

        out_red = ((fg_red * fg_alpha) + (bg_red * bg_alpha * (1.0 - fg_alpha))) / out_alpha
        out_green = ((fg_green * fg_alpha) + (bg_green * bg_alpha * (1.0 - fg_alpha))) / out_alpha
        out_blue = ((fg_blue * fg_alpha) + (bg_blue * bg_alpha * (1.0 - fg_alpha))) / out_alpha

        return ColorAll("srgb", [out_red, out_green, out_blue], alpha=out_alpha)

    def is_light_color(self, rgb: RGBColor) -> bool:
        """Return whether the configured RGB heuristic considers the color light."""
        registry = cast(_ContrastRegistryProtocol, self)
        heuristic = registry.get_rgb_heuristic(registry.heuristic_strategy)
        return heuristic.is_light(rgb)

    def luminance(self, rgb: RGBColor) -> float:
        """Return the configured heuristic luminance for an RGB tuple."""
        registry = cast(_ContrastRegistryProtocol, self)
        heuristic = registry.get_rgb_heuristic(registry.heuristic_strategy)
        return heuristic.luminance(rgb)

    def brighten_color(
        self,
        rgb: RGBColor,
        target_contrast: float,
        background_rgb: RGBColor,
    ) -> RGBColor:
        """Adjust an RGB color using the configured heuristic strategy."""
        registry = cast(_ContrastRegistryProtocol, self)
        heuristic = registry.get_rgb_heuristic(registry.heuristic_strategy)
        return heuristic.brighten(
            rgb,
            target_contrast=target_contrast,
            background_rgb=background_rgb,
            contrast_fn=self.contrast_ratio,
        )
