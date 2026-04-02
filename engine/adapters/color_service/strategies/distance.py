from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Sequence, cast

from coloraide.everything import ColorAll

if TYPE_CHECKING:
    from ..service import ColorLike


class DistanceStrategy(Protocol):
    """Contract for perceptual color distance strategies."""

    @property
    def name(self) -> str:
        ...

    def distance(self, left: ColorAll, right: ColorAll, *, method: str = "2000") -> float:
        ...


class DeltaEDistanceStrategy:
    """Delta E distance strategy powered by ColorAide."""

    name = "delta-e"

    def distance(self, left: ColorAll, right: ColorAll, *, method: str = "2000") -> float:
        return float(left.delta_e(right, method=method))


class _DistanceRegistryProtocol(Protocol):
    """Capabilities required by distance operations."""

    distance_strategy: str
    distance_method: str

    def get_distance(self, name: str) -> DistanceStrategy:
        ...

    def parse_color(self, value: ColorLike) -> ColorAll:
        ...


class DistanceOperationsMixin:
    """Distance helpers exposed by the registry."""

    def delta_e_distance(
        self,
        left: ColorLike,
        right: ColorLike,
        *,
        strategy_name: str | None = None,
        method: str | None = None,
    ) -> float:
        """Calculate the perceptual distance between two colors."""
        registry = cast(_DistanceRegistryProtocol, self)
        strategy = registry.get_distance(strategy_name or registry.distance_strategy)
        return strategy.distance(
            registry.parse_color(left),
            registry.parse_color(right),
            method=method or registry.distance_method,
        )

    def closest_with_distance(
        self,
        value: ColorLike,
        candidates: Sequence[ColorLike],
        *,
        strategy_name: str | None = None,
        method: str | None = None,
    ) -> tuple[ColorLike | None, float | None]:
        """Return the nearest candidate color and its distance."""
        if not candidates:
            return None, None

        best_candidate: ColorLike | None = None
        best_distance: float | None = None
        for candidate in candidates:
            distance = self.delta_e_distance(value, candidate, strategy_name=strategy_name, method=method)
            if best_distance is None or distance < best_distance:
                best_candidate = candidate
                best_distance = distance
        return best_candidate, best_distance
