from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping

from engine.domain.models.element import Element


@dataclass(frozen=True, slots=True)
class SnapshotOptions:
    wait_after_load_ms: int = 500
    include_invisible: bool = True
    include_user_agent_rules: bool = False
    capture_screenshot: bool = True
    initial_viewport_width: int = 1440
    initial_viewport_height: int = 900
    scroll_step_px: int = 900
    max_render_ready_checks: int = 8
    render_ready_interval_ms: int = 250


@dataclass(frozen=True, slots=True)
class RenderSnapshot:
    metadata: dict[str, Any]
    document: dict[str, Any]
    nodes: tuple[Element, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> "RenderSnapshot":
        return cls(
            metadata=dict(payload.get("metadata") or {}),
            document=dict(payload.get("document") or {}),
            nodes=tuple(
                node if isinstance(node, Element) else Element.build(node)
                for node in (payload.get("nodes") or ())
                if isinstance(node, (Element, Mapping))
            ),
        )

    def __iter__(self) -> Iterator[Element]:
        return iter(self.nodes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "document": self.document,
            "nodes": [node.to_dict() for node in self.nodes],
        }
