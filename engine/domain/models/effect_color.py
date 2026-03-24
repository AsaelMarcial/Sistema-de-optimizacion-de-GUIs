from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Self


@dataclass(frozen=True, slots=True)
class EffectColorTokenModel:
    value: str
    hex_value: str
    alpha: float
    color_id: str | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any] | None = None) -> Self:
        payload = payload or {}
        return cls(
            value=str(payload.get("value") or ""),
            hex_value=str(payload.get("hex") or payload.get("hex_value") or ""),
            alpha=float(payload.get("alpha") or 0.0),
            color_id=str(payload["color_id"]) if payload.get("color_id") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "value": self.value,
            "hex": self.hex_value,
            "alpha": round(self.alpha, 4),
        }
        if self.color_id is not None:
            payload["color_id"] = self.color_id
        return payload


@dataclass(frozen=True, slots=True)
class EffectColorEntryModel:
    effect_id: str
    element_id: str
    tag_name: str
    selector_hint: str | None
    property_name: str
    resolved_value: str
    style_id: str | None = None
    declaration_id: str | None = None
    declared_property: str | None = None
    colors: tuple[EffectColorTokenModel, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any] | None = None) -> Self:
        payload = payload or {}
        return cls(
            effect_id=str(payload.get("effect_id") or ""),
            element_id=str(payload.get("element_id") or ""),
            tag_name=str(payload.get("tag_name") or ""),
            selector_hint=(
                str(payload["selector_hint"]) if payload.get("selector_hint") is not None else None
            ),
            property_name=str(payload.get("property_name") or ""),
            resolved_value=str(payload.get("resolved_value") or ""),
            style_id=str(payload["style_id"]) if payload.get("style_id") is not None else None,
            declaration_id=(
                str(payload["declaration_id"])
                if payload.get("declaration_id") is not None
                else None
            ),
            declared_property=(
                str(payload["declared_property"])
                if payload.get("declared_property") is not None
                else None
            ),
            colors=tuple(
                EffectColorTokenModel.build(item)
                for item in (payload.get("colors") or ())
                if isinstance(item, Mapping)
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "effect_id": self.effect_id,
            "element_id": self.element_id,
            "tag_name": self.tag_name,
            "property_name": self.property_name,
            "resolved_value": self.resolved_value,
            "colors": [item.to_dict() for item in self.colors],
        }
        if self.selector_hint is not None:
            payload["selector_hint"] = self.selector_hint
        if self.style_id is not None:
            payload["style_id"] = self.style_id
        if self.declaration_id is not None:
            payload["declaration_id"] = self.declaration_id
        if self.declared_property is not None:
            payload["declared_property"] = self.declared_property
        return payload


@dataclass(frozen=True, slots=True)
class EffectColorReportModel:
    entries: tuple[EffectColorEntryModel, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any] | None = None) -> Self:
        payload = payload or {}
        return cls(
            entries=tuple(
                EffectColorEntryModel.build(item)
                for item in (payload.get("entries") or ())
                if isinstance(item, Mapping)
            ),
        )

    def __iter__(self):
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def to_dict(self) -> dict[str, Any]:
        by_property: dict[str, dict[str, Any]] = {}
        for entry in self.entries:
            bucket = by_property.setdefault(
                entry.property_name,
                {
                    "property_name": entry.property_name,
                    "entry_count": 0,
                    "distinct_hex_values": set(),
                },
            )
            bucket["entry_count"] += 1
            for color in entry.colors:
                if color.hex_value:
                    bucket["distinct_hex_values"].add(color.hex_value)

        property_rows = [
            {
                "property_name": property_name,
                "entry_count": bucket["entry_count"],
                "distinct_color_count": len(bucket["distinct_hex_values"]),
            }
            for property_name, bucket in by_property.items()
        ]
        property_rows.sort(key=lambda item: (-item["entry_count"], item["property_name"]))

        return {
            "count": len(self.entries),
            "entries": [entry.to_dict() for entry in self.entries],
            "by_property": property_rows,
        }
