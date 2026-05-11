from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Self

from engine.domain.enums.scope.css_properties import CssPropertyId, get_css_property
from engine.domain.enums.types.quality import ContrastBackgroundValidation


def _css_property_value(property_name: CssPropertyId | str | None) -> str:
    return property_name.value if isinstance(property_name, CssPropertyId) else str(property_name or "")


def _coerce_optional_css_property_id(value: CssPropertyId | str | None) -> CssPropertyId | str | None:
    if value is None:
        return None
    property_spec = get_css_property(value)
    if property_spec is not None:
        return property_spec
    normalized = str(value or "").strip().lower()
    return normalized or None


def _coerce_background_validation(
    value: ContrastBackgroundValidation | str | None,
) -> ContrastBackgroundValidation:
    if isinstance(value, ContrastBackgroundValidation):
        return value
    normalized = str(value or ContrastBackgroundValidation.UNVALIDATED.value).strip().lower()
    try:
        return ContrastBackgroundValidation(
            normalized or ContrastBackgroundValidation.UNVALIDATED.value
        )
    except ValueError:
        return ContrastBackgroundValidation.UNVALIDATED


@dataclass(frozen=True, slots=True)
class ContrastColorReference:
    css: str
    hex_value: str
    alpha: float
    color_id: str | None = None
    element_id: str | None = None
    style_id: str | None = None
    declaration_id: str | None = None
    property_name: CssPropertyId | str | None = None
    declared_property: CssPropertyId | str | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any] | None = None) -> Self:
        payload = payload or {}
        return cls(
            css=str(payload.get("css") or ""),
            hex_value=str(payload.get("hex") or payload.get("hex_value") or ""),
            alpha=float(payload.get("alpha") or 0.0),
            color_id=str(payload["color_id"]) if payload.get("color_id") is not None else None,
            element_id=str(payload["element_id"]) if payload.get("element_id") is not None else None,
            style_id=str(payload["style_id"]) if payload.get("style_id") is not None else None,
            declaration_id=(
                str(payload["declaration_id"])
                if payload.get("declaration_id") is not None
                else None
            ),
            property_name=(
                _coerce_optional_css_property_id(payload["property_name"])
                if payload.get("property_name") is not None
                else None
            ),
            declared_property=(
                _coerce_optional_css_property_id(payload["declared_property"])
                if payload.get("declared_property") is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "css": self.css,
            "hex": self.hex_value,
            "alpha": round(self.alpha, 4),
        }
        if self.color_id is not None:
            payload["color_id"] = self.color_id
        if self.element_id is not None:
            payload["element_id"] = self.element_id
        if self.style_id is not None:
            payload["style_id"] = self.style_id
        if self.declaration_id is not None:
            payload["declaration_id"] = self.declaration_id
        if self.property_name is not None:
            payload["property_name"] = _css_property_value(self.property_name)
        if self.declared_property is not None:
            payload["declared_property"] = _css_property_value(self.declared_property)
        return payload


@dataclass(frozen=True, slots=True)
class ContrastIssue:
    issue_id: str
    element_id: str | None
    selector: str
    tag_name: str
    text_sample: str
    contrast_ratio: float
    required_ratio: float
    is_large_text: bool
    font_size_px: float
    font_weight: int
    bounds: Mapping[str, Any] = field(default_factory=dict)
    foreground: ContrastColorReference = field(default_factory=lambda: ContrastColorReference("", "", 0.0))
    background: ContrastColorReference = field(default_factory=lambda: ContrastColorReference("", "", 0.0))
    background_validation: ContrastBackgroundValidation = ContrastBackgroundValidation.UNVALIDATED

    @classmethod
    def build(cls, payload: Mapping[str, Any] | None = None) -> Self:
        payload = payload or {}
        return cls(
            issue_id=str(payload.get("issue_id") or ""),
            element_id=str(payload["element_id"]) if payload.get("element_id") is not None else None,
            selector=str(payload.get("selector") or ""),
            tag_name=str(payload.get("tag_name") or ""),
            text_sample=str(payload.get("text_sample") or ""),
            contrast_ratio=float(payload.get("contrast_ratio") or 0.0),
            required_ratio=float(payload.get("required_ratio") or 0.0),
            is_large_text=bool(payload.get("is_large_text", False)),
            font_size_px=float(payload.get("font_size_px") or 0.0),
            font_weight=int(payload.get("font_weight") or 0),
            bounds=dict(payload.get("bounds") or {}),
            foreground=ContrastColorReference.build(
                payload.get("foreground") if isinstance(payload.get("foreground"), Mapping) else None
            ),
            background=ContrastColorReference.build(
                payload.get("background") if isinstance(payload.get("background"), Mapping) else None
            ),
            background_validation=_coerce_background_validation(payload.get("background_validation")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "issue_id": self.issue_id,
            "selector": self.selector,
            "tag_name": self.tag_name,
            "text_sample": self.text_sample,
            "contrast_ratio": round(self.contrast_ratio, 4),
            "required_ratio": round(self.required_ratio, 4),
            "font_size_px": round(self.font_size_px, 4),
            "font_weight": self.font_weight,
            "foreground": self.foreground.to_dict(),
            "background": self.background.to_dict(),
            "background_validation": self.background_validation.value,
        }
        if self.element_id is not None:
            payload["element_id"] = self.element_id
        if self.is_large_text:
            payload["is_large_text"] = True
        if self.bounds:
            payload["bounds"] = dict(self.bounds)
        return payload


@dataclass(frozen=True, slots=True)
class ContrastReport:
    issues: tuple[ContrastIssue, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any] | None = None) -> Self:
        payload = payload or {}
        return cls(
            issues=tuple(
                ContrastIssue.build(item)
                for item in (payload.get("issues") or ())
                if isinstance(item, Mapping)
            ),
        )

    def __iter__(self):
        return iter(self.issues)

    def __len__(self) -> int:
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
        }
