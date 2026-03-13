from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SnapshotOptions:
    wait_after_load_ms: int = 500
    include_invisible: bool = True
    include_user_agent_rules: bool = True
    include_color_frequencies: bool = False
    capture_screenshot: bool = True
    initial_viewport_width: int = 1440
    initial_viewport_height: int = 900
    scroll_step_px: int = 900
    max_stability_checks: int = 8
    stability_interval_ms: int = 250


@dataclass(frozen=True, slots=True)
class SnapshotNode:
    node_id: str
    backend_node_id: int
    document_order: int
    identity: dict[str, Any]
    layout: dict[str, Any]
    styles: dict[str, Any]
    flags: dict[str, Any]
    text: str | None = None
    parent_id: str | None = None
    children_ids: tuple[str, ...] = field(default_factory=tuple)
    paint_order: int | None = None
    style_trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RenderSnapshot:
    metadata: dict[str, Any]
    document: dict[str, Any]
    nodes: tuple[SnapshotNode, ...]
    rules_used: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    palette: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "document": self.document,
            "nodes": [node.to_dict() for node in self.nodes],
            "rules_used": list(self.rules_used),
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
