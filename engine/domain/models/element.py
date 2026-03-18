from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Mapping


@dataclass(frozen=True, slots=True)
class ElementInventoryEntry:
    node_id: str
    backend_node_id: int
    document_order: int
    identity: dict[str, Any]
    layout: dict[str, Any]
    styles: dict[str, Any]
    computed_styles: dict[str, Any]
    flags: dict[str, Any]
    text: str | None = None
    parent_id: str | None = None
    children_ids: tuple[str, ...] = field(default_factory=tuple)
    paint_order: int | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> "ElementInventoryEntry":
        return cls(
            node_id=str(payload.get("node_id") or ""),
            backend_node_id=int(payload.get("backend_node_id") or 0),
            document_order=int(payload.get("document_order") or 0),
            identity=dict(payload.get("identity") or {}),
            layout=dict(payload.get("layout") or {}),
            styles=dict(payload.get("styles") or {}),
            computed_styles=dict(payload.get("computed_styles") or {}),
            flags=dict(payload.get("flags") or {}),
            text=str(payload.get("text")) if payload.get("text") is not None else None,
            parent_id=str(payload.get("parent_id")) if payload.get("parent_id") is not None else None,
            children_ids=tuple(str(item) for item in (payload.get("children_ids") or ())),
            paint_order=int(payload["paint_order"]) if payload.get("paint_order") is not None else None,
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self.children_ids)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
