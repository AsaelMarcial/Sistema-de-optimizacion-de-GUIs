from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from coloraide.everything import ColorAll

if TYPE_CHECKING:
    from ..service import ColorLike


class PaletteStrategy(Protocol):
    @property
    def name(self) -> str:
        ...

    def tonal_color(
        self,
        seed: ColorAll,
        tone: float,
        *,
        chroma_override: float | None = None,
    ) -> ColorAll:
        ...


@dataclass(frozen=True)
class HCTPaletteStrategy:
    name: str = "hct"
    fit_method: str = "raytrace"
    perceptual_space: str = "hct"

    def tonal_color(
        self,
        seed: ColorAll,
        tone: float,
        *,
        chroma_override: float | None = None,
    ) -> ColorAll:
        tonal = seed.convert("hct").clone()
        if chroma_override is not None:
            tonal.set("chroma", float(chroma_override))
        tonal.set("tone", float(tone))
        return tonal.fit(space="srgb", method=self.fit_method, pspace=self.perceptual_space).convert("srgb")


class _PaletteRegistryProtocol(Protocol):
    palette_strategy: str
    palette_chroma_override: float | None

    def get_palette(self, name: str) -> PaletteStrategy:
        ...

    def parse_color(self, value: ColorLike) -> ColorAll:
        ...


class PaletteOperationsMixin:
    def tonal_color(
        self,
        value: ColorLike,
        tone: float,
        *,
        strategy_name: str | None = None,
        chroma_override: float | None = None,
    ) -> ColorAll:
        registry = cast(_PaletteRegistryProtocol, self)
        palette = registry.get_palette(strategy_name or registry.palette_strategy)
        return palette.tonal_color(
            registry.parse_color(value),
            float(tone),
            chroma_override=(
                chroma_override
                if chroma_override is not None
                else registry.palette_chroma_override
            ),
        )
