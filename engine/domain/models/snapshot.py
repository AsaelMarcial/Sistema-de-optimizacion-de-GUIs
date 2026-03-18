from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Mapping

from engine.domain.models.element import ElementInventoryEntry


@dataclass(frozen=True, slots=True)
class SnapshotOptions:
    wait_after_load_ms: int = 500
    include_invisible: bool = True
    include_user_agent_rules: bool = False
    include_color_frequencies: bool = False
    capture_screenshot: bool = True
    initial_viewport_width: int = 1440
    initial_viewport_height: int = 900
    scroll_step_px: int = 900
    max_stability_checks: int = 8
    stability_interval_ms: int = 250


@dataclass(frozen=True, slots=True)
class RenderSnapshot:
    metadata: dict[str, Any]
    document: dict[str, Any]
    elements_inventory: tuple[ElementInventoryEntry, ...]
    styles_inventory: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    palette: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> "RenderSnapshot":
        return cls(
            metadata=dict(payload.get("metadata") or {}),
            document=dict(payload.get("document") or {}),
            elements_inventory=tuple(
                ElementInventoryEntry.build(item)
                for item in (payload.get("elements_inventory") or ())
                if isinstance(item, Mapping)
            ),
            styles_inventory=tuple(
                dict(item)
                for item in (payload.get("styles_inventory") or ())
                if isinstance(item, Mapping)
            ),
            palette=tuple(
                dict(item)
                for item in (payload.get("palette") or ())
                if isinstance(item, Mapping)
            ),
        )

    def __iter__(self) -> Iterator[ElementInventoryEntry]:
        return iter(self.elements_inventory)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "document": self.document,
            "elements_inventory": [node.to_dict() for node in self.elements_inventory],
            "styles_inventory": list(self.styles_inventory),
            "palette": list(self.palette),
        }


@dataclass(frozen=True, slots=True)
class RenderArtifacts:
    screenshot_path: str | None
    snapshot: RenderSnapshot
    snapshot_json_path: str | None
    color_frequencies: list[dict[str, Any]] | None = None


def snapshot_options_to_dict(options: SnapshotOptions) -> dict[str, Any]:
    return asdict(options)
