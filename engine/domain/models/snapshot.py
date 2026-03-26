from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Mapping

from engine.domain.models.color import ColorInventoryModel
from engine.domain.models.element import ElementInventoryEntry, ElementInventoryModel
from engine.domain.models.style import StyleInventoryModel


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
    nodes: tuple[ElementInventoryEntry, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> "RenderSnapshot":
        nodes_payload = payload.get("nodes") or payload.get("elements") or ()
        if not nodes_payload and payload.get("tree"):
            nodes_payload = _flatten_tree_payload(payload.get("tree") or ())
        return cls(
            metadata=dict(payload.get("metadata") or {}),
            document=dict(payload.get("document") or {}),
            nodes=tuple(
                node if isinstance(node, ElementInventoryEntry) else ElementInventoryEntry.build(node)
                for node in nodes_payload
                if isinstance(node, (ElementInventoryEntry, Mapping))
            ),
        )

    def build_elements_inventory(self) -> ElementInventoryModel:
        return ElementInventoryModel.build(self.nodes)

    def __iter__(self) -> Iterator[ElementInventoryEntry]:
        return iter(self.nodes)

    def to_dict(self) -> dict[str, Any]:
        elements_inventory = self.build_elements_inventory()
        return {
            "metadata": self.metadata,
            "document": self.document,
            "tree": list(elements_inventory.to_tree()),
        }


@dataclass(frozen=True, slots=True)
class RenderArtifacts:
    screenshot_path: str | None
    snapshot: RenderSnapshot
    snapshot_json_path: str | None
    color_frequencies: list[dict[str, Any]] | None = None
    elements_inventory: ElementInventoryModel | None = None
    styles_inventory_seed: StyleInventoryModel | None = None
    colors_inventory_seed: ColorInventoryModel | None = None
    css_overview: dict[str, Any] | None = None


def snapshot_options_to_dict(options: SnapshotOptions) -> dict[str, Any]:
    return asdict(options)


def _flatten_tree_payload(nodes_payload: Any) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []

    def _visit(node_payload: Any, parent_id: str | None = None) -> None:
        if not isinstance(node_payload, Mapping):
            return
        normalized = dict(node_payload)
        children_payload = tuple(normalized.pop("children", ()) or ())
        if parent_id is not None and normalized.get("parent_id") is None:
            normalized["parent_id"] = parent_id
        if children_payload and not normalized.get("children_ids"):
            child_ids = [
                str(child.get("node_id") or "").strip()
                for child in children_payload
                if isinstance(child, Mapping) and str(child.get("node_id") or "").strip()
            ]
            if child_ids:
                normalized["children_ids"] = child_ids
        flattened.append(normalized)
        current_id = str(normalized.get("node_id") or "").strip() or parent_id
        for child_payload in children_payload:
            _visit(child_payload, current_id)

    for node_payload in nodes_payload or ():
        _visit(node_payload)

    return flattened
