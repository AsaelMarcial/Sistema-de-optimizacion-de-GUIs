from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterator, Mapping, Self

from engine.domain.enums.types.style import (
    StyleKind,
    StyleOrigin,
    StyleResolutionStatus,
    StyleUsageStatus,
)


def _coerce_style_kind(value: StyleKind | str | None) -> StyleKind:
    if isinstance(value, StyleKind):
        return value
    normalized = str(value or StyleKind.EMBEDDED.value).strip().lower()
    if normalized == "matched":
        normalized = StyleKind.EMBEDDED.value
    if normalized == "attributes":
        normalized = StyleKind.INLINE.value
    return StyleKind(normalized)


def _coerce_style_origin(value: StyleOrigin | str | None) -> StyleOrigin | None:
    if value is None:
        return None
    if isinstance(value, StyleOrigin):
        return value
    normalized = str(value).strip().lower()
    return StyleOrigin(normalized) if normalized else None


def _coerce_style_usage_status(
    value: StyleUsageStatus | str | None,
) -> StyleUsageStatus:
    if isinstance(value, StyleUsageStatus):
        return value
    normalized = str(value or StyleUsageStatus.UNKNOWN.value).strip().lower()
    return StyleUsageStatus(normalized)


def _coerce_style_resolution_status(
    value: StyleResolutionStatus | str | None,
) -> StyleResolutionStatus | None:
    if value is None:
        return None
    if isinstance(value, StyleResolutionStatus):
        return value
    normalized = str(value).strip().lower()
    return StyleResolutionStatus(normalized) if normalized else None


@dataclass(frozen=True, slots=True)
class StyleSourceRangeModel:
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            start_line=int(payload.get("start_line") or 0),
            start_column=int(payload.get("start_column") or 0),
            end_line=int(payload.get("end_line") or 0),
            end_column=int(payload.get("end_column") or 0),
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "start_line": self.start_line,
            "start_column": self.start_column,
            "end_line": self.end_line,
            "end_column": self.end_column,
        }


@dataclass(frozen=True, slots=True)
class StyleDeclarationModel:
    name: str
    value: str
    important: bool = False
    implicit: bool = False
    declaration_id: str | None = None
    declaration_order: int | None = None
    usage_status: StyleUsageStatus = StyleUsageStatus.UNKNOWN
    element_usage_count: int = 0
    longhand_properties: tuple[str, ...] = field(default_factory=tuple)
    used_by_element_ids: tuple[str, ...] = field(default_factory=tuple)
    parse_status: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "usage_status",
            _coerce_style_usage_status(self.usage_status),
        )

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            name=str(payload.get("name") or payload.get("property_name") or ""),
            value=str(payload.get("value") or payload.get("raw_value") or ""),
            important=bool(payload.get("important", False)),
            implicit=bool(payload.get("implicit", False)),
            declaration_id=(
                str(payload["declaration_id"])
                if payload.get("declaration_id") is not None
                else None
            ),
            declaration_order=(
                int(payload["declaration_order"])
                if payload.get("declaration_order") is not None
                else None
            ),
            usage_status=_coerce_style_usage_status(payload.get("usage_status")),
            element_usage_count=int(payload.get("element_usage_count") or 0),
            longhand_properties=tuple(
                str(item) for item in (payload.get("longhand_properties") or ())
            ),
            used_by_element_ids=tuple(
                str(item) for item in (payload.get("used_by_element_ids") or ())
            ),
            parse_status=(
                str(payload["parse_status"])
                if payload.get("parse_status") is not None
                else None
            ),
        )

    def matches_property(self, property_name: str) -> bool:
        return self.name == property_name

    def with_identifier(self, declaration_id: str) -> Self:
        return replace(self, declaration_id=declaration_id)

    def with_usage(
        self,
        *,
        used_by_element_ids: tuple[str, ...],
        usage_status: StyleUsageStatus | str,
        element_usage_count: int,
    ) -> Self:
        return replace(
            self,
            used_by_element_ids=used_by_element_ids,
            usage_status=usage_status,
            element_usage_count=element_usage_count,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
        }
        if self.declaration_id is not None:
            payload["declaration_id"] = self.declaration_id
        if self.important:
            payload["important"] = True
        if self.implicit:
            payload["implicit"] = True
        if self.element_usage_count:
            payload["element_usage_count"] = self.element_usage_count
        if self.used_by_element_ids:
            payload["used_by_element_ids"] = list(self.used_by_element_ids)
        if self.parse_status is not None:
            payload["parse_status"] = self.parse_status
        return payload

    def to_builder_dict(self) -> dict[str, Any]:
        payload = self.to_dict()
        if self.declaration_order is not None:
            payload["declaration_order"] = self.declaration_order
        if self.longhand_properties:
            payload["longhand_properties"] = list(self.longhand_properties)
        return payload


@dataclass(frozen=True, slots=True)
class ComputedStyleValueModel:
    computed_value: str
    style_id: str | None = None
    kind: StyleKind | None = None
    declared_property: str | None = None
    declaration_id: str | None = None
    inherited_from_element_id: str | None = None
    resolution_status: StyleResolutionStatus | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _coerce_style_kind(self.kind) if self.kind else None)
        object.__setattr__(
            self,
            "resolution_status",
            _coerce_style_resolution_status(self.resolution_status),
        )

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            computed_value=str(payload.get("computed_value") or ""),
            style_id=str(payload["style_id"]) if payload.get("style_id") is not None else None,
            kind=(
                _coerce_style_kind(payload["kind"])
                if payload.get("kind") is not None
                else None
            ),
            declared_property=(
                str(payload["declared_property"])
                if payload.get("declared_property") is not None
                else None
            ),
            declaration_id=(
                str(payload["declaration_id"])
                if payload.get("declaration_id") is not None
                else None
            ),
            inherited_from_element_id=(
                str(payload["inherited_from_element_id"])
                if payload.get("inherited_from_element_id") is not None
                else None
            ),
            resolution_status=_coerce_style_resolution_status(payload.get("resolution_status")),
        )

    def is_resolved(self) -> bool:
        return self.resolution_status == StyleResolutionStatus.EXACT_MATCH

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.style_id is not None:
            payload["style_id"] = self.style_id
        if self.kind is not None:
            payload["kind"] = self.kind.value
        if self.declared_property is not None:
            payload["declared_property"] = self.declared_property
        if self.inherited_from_element_id is not None:
            payload["inherited_from_element_id"] = self.inherited_from_element_id
        if self.resolution_status is not None:
            payload["resolution_status"] = self.resolution_status.value
        payload["computed_value"] = self.computed_value
        return payload


@dataclass(frozen=True, slots=True)
class StyleInventoryEntry:
    style_id: str
    kind: StyleKind
    declarations: tuple[StyleDeclarationModel, ...]
    origin: StyleOrigin | None = None
    style_sheet_id: str | None = None
    selector_text: str | None = None
    source_range: StyleSourceRangeModel | None = None
    layer_name: str | None = None
    layer_order: int | None = None
    source_url: str | None = None
    node_ids: tuple[str, ...] = field(default_factory=tuple)
    usage_count: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _coerce_style_kind(self.kind))
        object.__setattr__(self, "origin", _coerce_style_origin(self.origin))

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            style_id=str(payload.get("style_id") or ""),
            kind=_coerce_style_kind(payload.get("kind")),
            declarations=tuple(
                item
                if isinstance(item, StyleDeclarationModel)
                else StyleDeclarationModel.build(item)
                for item in (payload.get("declarations") or ())
                if isinstance(item, (StyleDeclarationModel, Mapping))
            ),
            origin=_coerce_style_origin(payload.get("origin")),
            style_sheet_id=(
                str(payload["style_sheet_id"])
                if payload.get("style_sheet_id") is not None
                else None
            ),
            selector_text=(
                str(payload["selector_text"])
                if payload.get("selector_text") is not None
                else None
            ),
            source_range=(
                StyleSourceRangeModel.build(payload["source_range"])
                if isinstance(payload.get("source_range"), Mapping)
                else None
            ),
            layer_name=str(payload["layer_name"]) if payload.get("layer_name") is not None else None,
            layer_order=(
                int(payload["layer_order"])
                if payload.get("layer_order") is not None
                else None
            ),
            source_url=str(payload["source_url"]) if payload.get("source_url") is not None else None,
            node_ids=tuple(str(item) for item in (payload.get("node_ids") or ())),
            usage_count=int(payload.get("usage_count") or 0),
        )

    def __iter__(self) -> Iterator[StyleDeclarationModel]:
        return iter(self.declarations)

    def declaration_for(self, property_name: str) -> StyleDeclarationModel | None:
        return next((item for item in self.declarations if item.matches_property(property_name)), None)

    def with_declarations(self, declarations: tuple[StyleDeclarationModel, ...]) -> Self:
        return replace(self, declarations=declarations)

    def signature(self) -> tuple[Any, ...]:
        return (
            self.kind,
            self.origin,
            self.style_sheet_id,
            self.selector_text,
            tuple(sorted((self.source_range.to_dict() if self.source_range else {}).items())),
            self.layer_name,
            self.layer_order,
            self.source_url,
            tuple(
                (
                    declaration.name,
                    declaration.value,
                    declaration.important,
                    declaration.implicit,
                )
                for declaration in self.declarations
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "style_id": self.style_id,
            "kind": self.kind.value,
            "declarations": [item.to_dict() for item in self.declarations],
        }
        if self.node_ids:
            payload["node_ids"] = list(self.node_ids)
        if self.usage_count:
            payload["usage_count"] = self.usage_count
        if self.origin is not None:
            payload["origin"] = self.origin.value
        if self.style_sheet_id is not None:
            payload["style_sheet_id"] = self.style_sheet_id
        if self.selector_text is not None:
            payload["selector_text"] = self.selector_text
        if self.source_range is not None:
            payload["source_range"] = self.source_range.to_dict()
        if self.layer_name is not None:
            payload["layer_name"] = self.layer_name
        if self.layer_order is not None:
            payload["layer_order"] = self.layer_order
        if self.source_url is not None:
            payload["source_url"] = self.source_url
        return payload


@dataclass(frozen=True, slots=True)
class StyleInventoryModel:
    entries: tuple[StyleInventoryEntry, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payloads: Any) -> Self:
        if not payloads:
            return cls()

        entries = tuple(
            payload
            if isinstance(payload, StyleInventoryEntry)
            else StyleInventoryEntry.build(payload)
            for payload in payloads
            if isinstance(payload, (StyleInventoryEntry, Mapping))
        )
        deduped: dict[tuple[Any, ...], StyleInventoryEntry] = {}
        for entry in entries:
            deduped.setdefault(entry.signature(), entry)
        ordered_entries = tuple(sorted(deduped.values(), key=lambda item: (item.style_id, item.kind)))
        return cls(entries=ordered_entries)

    @classmethod
    def build_from_aggregate(
        cls,
        aggregate: Mapping[tuple[Any, ...], Mapping[str, Any]],
    ) -> tuple[Self, dict[tuple[Any, ...], str]]:
        if not aggregate:
            return cls(), {}

        sorted_keys = sorted(
            aggregate,
            key=lambda key: (
                aggregate[key]["_sort_key"],
                aggregate[key].get("selector_text") or "",
                aggregate[key].get("kind") or "",
            ),
        )
        style_ids_by_key = {
            key: f"style-{index}"
            for index, key in enumerate(sorted_keys, start=1)
        }

        entries: list[StyleInventoryEntry] = []
        for key in sorted_keys:
            aggregate_entry = aggregate[key]
            style_id = style_ids_by_key[key]
            used_by_element_ids = tuple(sorted(str(item) for item in aggregate_entry.get("node_ids") or ()))
            declarations = tuple(
                StyleDeclarationModel.build(item).with_identifier(f"{style_id}-decl-{index}")
                .with_usage(
                    used_by_element_ids=used_by_element_ids,
                    usage_status="used" if used_by_element_ids else "unknown",
                    element_usage_count=len(used_by_element_ids),
                )
                for index, item in enumerate(aggregate_entry.get("declarations") or (), start=1)
                if isinstance(item, Mapping)
            )
            entries.append(
                StyleInventoryEntry.build(
                    {
                        "style_id": style_id,
                        "kind": aggregate_entry.get("kind") or "",
                        "origin": aggregate_entry.get("origin"),
                        "style_sheet_id": aggregate_entry.get("style_sheet_id"),
                        "selector_text": aggregate_entry.get("selector_text"),
                        "declarations": declarations,
                        "source_range": aggregate_entry.get("source_range"),
                        "layer_name": aggregate_entry.get("layer_name"),
                        "layer_order": aggregate_entry.get("layer_order"),
                        "source_url": aggregate_entry.get("source_url"),
                        "node_ids": used_by_element_ids,
                        "usage_count": int(aggregate_entry.get("usage_count") or 0),
                    }
                )
            )

        return cls(entries=tuple(entries)), style_ids_by_key

    def __iter__(self) -> Iterator[StyleInventoryEntry]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def entry_by_id(self, style_id: str) -> StyleInventoryEntry | None:
        return next((entry for entry in self.entries if entry.style_id == style_id), None)

    def declaration_by_id(self, declaration_id: str) -> StyleDeclarationModel | None:
        return next(
            (
                declaration
                for entry in self.entries
                for declaration in entry.declarations
                if declaration.declaration_id == declaration_id
            ),
            None,
        )

    def to_dict(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]


StyleModel = StyleInventoryEntry
