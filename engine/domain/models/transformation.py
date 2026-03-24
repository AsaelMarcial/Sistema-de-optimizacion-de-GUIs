from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Mapping, Self

from engine.domain.enums.types.transformations import (
    TransformationKind,
    TransformationStatus,
)


def _coerce_transformation_kind(
    value: TransformationKind | str | None,
) -> TransformationKind:
    if isinstance(value, TransformationKind):
        return value
    normalized = str(value or TransformationKind.HEURISTIC.value).strip().lower()
    return TransformationKind(normalized)


def _coerce_transformation_status(
    value: TransformationStatus | str | None,
) -> TransformationStatus:
    if isinstance(value, TransformationStatus):
        return value
    normalized = str(value or TransformationStatus.APPLIED.value).strip().lower()
    return TransformationStatus(normalized)

@dataclass(frozen=True, slots=True)
class TransformationTargetModel:
    node_id: str | None
    file_path: str | None
    property_name: str
    before_value: str | None = None
    after_value: str | None = None
    selector_hint: str | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            node_id=str(payload["node_id"]) if payload.get("node_id") is not None else None,
            file_path=str(payload["file_path"]) if payload.get("file_path") is not None else None,
            property_name=str(payload.get("property_name") or payload.get("property") or ""),
            before_value=(
                str(payload["before_value"])
                if payload.get("before_value") is not None
                else None
            ),
            after_value=(
                str(payload["after_value"])
                if payload.get("after_value") is not None
                else None
            ),
            selector_hint=(
                str(payload["selector_hint"])
                if payload.get("selector_hint") is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"property_name": self.property_name}
        if self.node_id is not None:
            payload["node_id"] = self.node_id
        if self.file_path is not None:
            payload["file_path"] = self.file_path
        if self.before_value is not None:
            payload["before_value"] = self.before_value
        if self.after_value is not None:
            payload["after_value"] = self.after_value
        if self.selector_hint is not None:
            payload["selector_hint"] = self.selector_hint
        return payload


@dataclass(frozen=True, slots=True)
class TransformationModel:
    transformation_id: str
    transformation_kind: TransformationKind
    description: str
    targets: tuple[TransformationTargetModel, ...] = field(default_factory=tuple)
    status: TransformationStatus = TransformationStatus.APPLIED
    rationale: str | None = None
    estimated_savings_percent: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "transformation_kind",
            _coerce_transformation_kind(self.transformation_kind),
        )
        object.__setattr__(
            self,
            "status",
            _coerce_transformation_status(self.status),
        )

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            transformation_id=str(payload.get("transformation_id") or ""),
            transformation_kind=_coerce_transformation_kind(
                payload.get("transformation_kind") or payload.get("kind")
            ),
            description=str(payload.get("description") or ""),
            targets=tuple(
                TransformationTargetModel.build(item)
                for item in (payload.get("targets") or ())
                if isinstance(item, Mapping)
            ),
            status=_coerce_transformation_status(payload.get("status")),
            rationale=str(payload["rationale"]) if payload.get("rationale") is not None else None,
            estimated_savings_percent=(
                float(payload["estimated_savings_percent"])
                if payload.get("estimated_savings_percent") is not None
                else None
            ),
            metadata=dict(payload.get("metadata") or {}),
        )

    def __iter__(self) -> Iterator[TransformationTargetModel]:
        return iter(self.targets)

    def add_target(self, target: TransformationTargetModel) -> Self:
        return type(self)(
            transformation_id=self.transformation_id,
            transformation_kind=self.transformation_kind,
            description=self.description,
            targets=(*self.targets, target),
            rationale=self.rationale,
            estimated_savings_percent=self.estimated_savings_percent,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "transformation_id": self.transformation_id,
            "transformation_kind": self.transformation_kind.value,
            "description": self.description,
            "targets": [target.to_dict() for target in self.targets],
            "status": self.status.value,
        }
        if self.rationale is not None:
            payload["rationale"] = self.rationale
        if self.estimated_savings_percent is not None:
            payload["estimated_savings_percent"] = round(self.estimated_savings_percent, 4)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


@dataclass(frozen=True, slots=True)
class TransformationInventoryModel:
    entries: tuple[TransformationModel, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payloads: Any) -> Self:
        if not payloads:
            return cls()
        entries = tuple(
            payload
            if isinstance(payload, TransformationModel)
            else TransformationModel.build(payload)
            for payload in payloads
            if isinstance(payload, (TransformationModel, Mapping))
        )
        deduped: dict[str, TransformationModel] = {}
        for entry in entries:
            deduped[entry.transformation_id] = entry
        ordered_entries = tuple(
            sorted(deduped.values(), key=lambda item: (item.transformation_kind, item.transformation_id))
        )
        return cls(entries=ordered_entries)

    def __iter__(self) -> Iterator[TransformationModel]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def entry_by_id(self, transformation_id: str) -> TransformationModel | None:
        return next(
            (entry for entry in self.entries if entry.transformation_id == transformation_id),
            None,
        )

    def to_dict(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]
