from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Self


@dataclass(frozen=True, slots=True)
class TagUsageModel:
    tag: str
    count: int

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            tag=str(payload.get("tag") or ""),
            count=int(payload.get("count") or 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "count": self.count}


@dataclass(frozen=True, slots=True)
class PropertyUsageModel:
    property_name: str
    total_count: int
    tags: tuple[TagUsageModel, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            property_name=str(payload.get("property") or payload.get("property_name") or ""),
            total_count=int(payload.get("total_count") or 0),
            tags=tuple(
                TagUsageModel.build(item)
                for item in (payload.get("tags") or ())
                if isinstance(item, Mapping)
            ),
        )

    def __iter__(self) -> Iterator[TagUsageModel]:
        return iter(self.tags)

    def to_dict(self) -> dict[str, Any]:
        return {
            "property": self.property_name,
            "total_count": self.total_count,
            "tags": [item.to_dict() for item in self.tags],
        }
