from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Self

from engine.domain.enums.scope.css_properties import (
    CssColorRole,
    CssPropertyCategory,
    get_css_property,
)
from engine.domain.models.style import ResolvedStyleValue


def classify_property(property_name: str) -> str:
    spec = get_css_property(property_name)
    if spec is None:
        return "other"
    if CssPropertyCategory.EFFECT in spec.categories:
        return "effect"
    if spec.color_role == CssColorRole.BACKGROUND:
        return "background"
    if spec.color_role == CssColorRole.FOREGROUND:
        return "foreground"
    return "other"


def classify_element(properties: tuple["Property", ...]) -> str:
    seen = {property_model.classification for property_model in properties}
    for candidate in ("background", "foreground", "effect", "other"):
        if candidate in seen:
            return candidate
    return "other"

@dataclass(frozen=True, slots=True)
class Property:
    name: str
    value: str
    classification: str = "other"
    color_id: str | None = None
    style_id: str | None = None
    declaration_id: str | None = None
    declared_property: str | None = None
    inherited_from_element_id: str | None = None
    resolution_status: str | None = None
    authored_value: str | None = None
    token_ids: tuple[str, ...] = field(default_factory=tuple)
    applied_token_id: str | None = None
    token_alias_to: str | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        name = str(payload.get("name") or "").strip().lower()
        value = str(payload.get("value") or "")
        classification = str(payload.get("classification") or "").strip().lower()
        return cls(
            name=name,
            value=value,
            classification=classification or classify_property(name),
            color_id=str(payload["color_id"]) if payload.get("color_id") is not None else None,
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
            inherited_from_element_id=(
                str(payload["inherited_from_element_id"])
                if payload.get("inherited_from_element_id") is not None
                else None
            ),
            resolution_status=(
                str(payload["resolution_status"])
                if payload.get("resolution_status") is not None
                else None
            ),
            authored_value=(
                str(payload["authored_value"])
                if payload.get("authored_value") is not None
                else None
            ),
            token_ids=tuple(
                dict.fromkeys(
                    str(item).strip()
                    for item in (payload.get("token_ids") or ())
                    if str(item).strip()
                )
            ),
            applied_token_id=(
                str(payload["applied_token_id"])
                if payload.get("applied_token_id") is not None
                else None
            ),
            token_alias_to=(
                str(payload["token_alias_to"])
                if payload.get("token_alias_to") is not None
                else None
            ),
        )

    @classmethod
    def from_computed_style(
        cls,
        *,
        name: str,
        computed_style: ResolvedStyleValue,
        color_id: str | None = None,
        authored_value: str | None = None,
        classification: str | None = None,
    ) -> Self:
        normalized_name = str(name or "").strip().lower()
        return cls(
            name=normalized_name,
            value=str(computed_style.computed_value or ""),
            classification=classification or classify_property(normalized_name),
            color_id=color_id,
            style_id=computed_style.style_id,
            declaration_id=computed_style.declaration_id,
            declared_property=computed_style.declared_property,
            inherited_from_element_id=computed_style.inherited_from_element_id,
            resolution_status=(
                getattr(computed_style.resolution_status, "value", computed_style.resolution_status)
                if computed_style.resolution_status is not None
                else None
            ),
            authored_value=authored_value,
        )

    def with_token_assignment(
        self,
        token_id: str,
        *,
        alias_to: str | None = None,
        applied: bool = True,
    ) -> Self:
        normalized_token_id = str(token_id or "").strip()
        if not normalized_token_id:
            return self
        return type(self)(
            name=self.name,
            value=self.value,
            classification=self.classification,
            color_id=self.color_id,
            style_id=self.style_id,
            declaration_id=self.declaration_id,
            declared_property=self.declared_property,
            inherited_from_element_id=self.inherited_from_element_id,
            resolution_status=self.resolution_status,
            authored_value=self.authored_value,
            token_ids=tuple(dict.fromkeys((*self.token_ids, normalized_token_id)).keys()),
            applied_token_id=normalized_token_id if applied else self.applied_token_id,
            token_alias_to=alias_to if alias_to is not None else self.token_alias_to,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "classification": self.classification,
        }
        if self.color_id is not None:
            payload["color_id"] = self.color_id
        if self.style_id is not None:
            payload["style_id"] = self.style_id
        if self.declaration_id is not None:
            payload["declaration_id"] = self.declaration_id
        if self.declared_property is not None:
            payload["declared_property"] = self.declared_property
        if self.inherited_from_element_id is not None:
            payload["inherited_from_element_id"] = self.inherited_from_element_id
        if self.resolution_status is not None:
            payload["resolution_status"] = self.resolution_status
        if self.authored_value is not None:
            payload["authored_value"] = self.authored_value
        if self.token_ids:
            payload["token_ids"] = list(self.token_ids)
        if self.applied_token_id is not None:
            payload["applied_token_id"] = self.applied_token_id
        if self.token_alias_to is not None:
            payload["token_alias_to"] = self.token_alias_to
        return payload


@dataclass(frozen=True, slots=True)
class Element:
    node_id: str
    backend_node_id: int
    parent_id: str | None
    children_ids: tuple[str, ...]
    document_order: int
    tag_name: str
    node_name: str
    html_id: str | None = None
    name: str | None = None
    role: str | None = None
    class_names: tuple[str, ...] = field(default_factory=tuple)
    data_attributes: dict[str, str] = field(default_factory=dict)
    attributes: dict[str, str] = field(default_factory=dict)
    selector: str | None = None
    xpath: str | None = None
    related_media: dict[str, Any] = field(default_factory=dict)
    text: str | None = None
    paint_order: int | None = None
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0
    is_visible: bool = False
    is_leaf: bool = False
    has_siblings: bool = False
    is_text_node: bool = False
    is_out_of_scope: bool = False
    is_stacking_context: bool = False
    effective_background: str | None = None
    properties: tuple[Property, ...] = field(default_factory=tuple)
    token_ids: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            node_id=str(payload.get("node_id") or "").strip(),
            backend_node_id=int(payload.get("backend_node_id") or 0),
            parent_id=str(payload["parent_id"]) if payload.get("parent_id") is not None else None,
            children_ids=tuple(
                str(item).strip()
                for item in (payload.get("children_ids") or ())
                if str(item).strip()
            ),
            document_order=int(payload.get("document_order") or 0),
            tag_name=str(payload.get("tag_name") or "").strip().lower(),
            node_name=str(payload.get("node_name") or "").strip(),
            html_id=str(payload["html_id"]) if payload.get("html_id") is not None else None,
            name=str(payload["name"]) if payload.get("name") is not None else None,
            role=str(payload["role"]) if payload.get("role") is not None else None,
            class_names=tuple(
                str(item).strip()
                for item in (payload.get("class_names") or ())
                if str(item).strip()
            ),
            data_attributes={
                str(key): str(value)
                for key, value in dict(payload.get("data_attributes") or {}).items()
            },
            attributes={
                str(key): str(value)
                for key, value in dict(payload.get("attributes") or {}).items()
            },
            selector=str(payload["selector"]) if payload.get("selector") is not None else None,
            xpath=str(payload["xpath"]) if payload.get("xpath") is not None else None,
            related_media=dict(payload.get("related_media") or {}),
            text=str(payload["text"]) if payload.get("text") is not None else None,
            paint_order=int(payload["paint_order"]) if payload.get("paint_order") is not None else None,
            x=float(payload.get("x") or 0.0),
            y=float(payload.get("y") or 0.0),
            width=float(payload.get("width") or 0.0),
            height=float(payload.get("height") or 0.0),
            left=float(payload.get("left") or 0.0),
            top=float(payload.get("top") or 0.0),
            right=float(payload.get("right") or 0.0),
            bottom=float(payload.get("bottom") or 0.0),
            is_visible=bool(payload.get("is_visible", False)),
            is_leaf=bool(payload.get("is_leaf", False)),
            has_siblings=bool(payload.get("has_siblings", False)),
            is_text_node=bool(payload.get("is_text_node", False)),
            is_out_of_scope=bool(payload.get("is_out_of_scope", False)),
            is_stacking_context=bool(payload.get("is_stacking_context", False)),
            effective_background=(
                str(payload["effective_background"])
                if payload.get("effective_background") is not None
                else None
            ),
            properties=tuple(
                property_payload
                if isinstance(property_payload, Property)
                else Property.build(property_payload)
                for property_payload in (payload.get("properties") or ())
                if isinstance(property_payload, (Property, Mapping))
            ),
            token_ids=tuple(
                dict.fromkeys(
                    str(item).strip()
                    for item in (payload.get("token_ids") or ())
                    if str(item).strip()
                )
            ),
        )

    def with_properties(self, properties: tuple[Property, ...]) -> Self:
        return replace(self, properties=properties)

    def with_token_assignment(self, token_id: str) -> Self:
        normalized_token_id = str(token_id or "").strip()
        if not normalized_token_id:
            return self
        return replace(
            self,
            token_ids=tuple(dict.fromkeys((*self.token_ids, normalized_token_id)).keys()),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "node_id": self.node_id,
            "backend_node_id": self.backend_node_id,
            "children_ids": list(self.children_ids),
            "document_order": self.document_order,
            "tag_name": self.tag_name,
            "node_name": self.node_name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
            "is_visible": self.is_visible,
            "is_leaf": self.is_leaf,
            "has_siblings": self.has_siblings,
            "is_text_node": self.is_text_node,
            "is_out_of_scope": self.is_out_of_scope,
            "is_stacking_context": self.is_stacking_context,
            "properties": [property_model.to_dict() for property_model in self.properties],
        }
        if self.token_ids:
            payload["token_ids"] = list(self.token_ids)
        if self.parent_id is not None:
            payload["parent_id"] = self.parent_id
        if self.html_id is not None:
            payload["html_id"] = self.html_id
        if self.name is not None:
            payload["name"] = self.name
        if self.role is not None:
            payload["role"] = self.role
        if self.class_names:
            payload["class_names"] = list(self.class_names)
        if self.data_attributes:
            payload["data_attributes"] = dict(self.data_attributes)
        if self.attributes:
            payload["attributes"] = dict(self.attributes)
        if self.selector is not None:
            payload["selector"] = self.selector
        if self.xpath is not None:
            payload["xpath"] = self.xpath
        if self.related_media:
            payload["related_media"] = dict(self.related_media)
        if self.text is not None:
            payload["text"] = self.text
        if self.paint_order is not None:
            payload["paint_order"] = self.paint_order
        if self.effective_background is not None:
            payload["effective_background"] = self.effective_background
        return payload
