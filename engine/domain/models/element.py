from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Mapping, Self

from engine.adapters.color_service import color_registry
from engine.domain.enums.scope.css_properties import (
    CATEGORY,
    ROLE,
    CSS_PROPERTIES,
    Category,
    Role,
    getColorSupportedProperties,
)
from engine.domain.enums.types.elements import PropertyClassification

_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_FUNCTION_COLOR_RE = re.compile(r"(?:rgba?|hsla?)\([^)]+\)", re.IGNORECASE)
_COMPOSITE_COLOR_PROPERTIES = frozenset(
    {
        "background",
        "border",
        "caret",
        "column-rule",
        "outline",
        "text-decoration",
        "text-emphasis",
        "-webkit-text-stroke",
    }
)
_EFFECT_COLOR_PROPERTIES = frozenset(
    {
        "background-image",
        "backdrop-filter",
        "border-image",
        "border-image-source",
        "box-shadow",
        "filter",
        "mask",
        "mask-border",
        "mask-border-source",
        "mask-image",
        "text-shadow",
    }
)
_PURE_COLOR_PROPERTIES = frozenset(
    property_name
    for property_name in getColorSupportedProperties()
    if property_name not in _COMPOSITE_COLOR_PROPERTIES
    and property_name not in _EFFECT_COLOR_PROPERTIES
)
_COLOR_VALUE_PROPERTIES = _PURE_COLOR_PROPERTIES | _COMPOSITE_COLOR_PROPERTIES


def _normalize_property_name(value: str | None) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    if normalized.startswith("--"):
        return normalized
    return normalized.lower()


def _property_data(property_name: str | None) -> Mapping[str, object] | None:
    normalized_name = _normalize_property_name(property_name)
    if not normalized_name:
        return None
    return CSS_PROPERTIES.get(normalized_name)


def _coerce_css_property_name(value: str | None) -> str:
    return _normalize_property_name(value)


def _coerce_optional_css_property_name(value: str | None) -> str | None:
    if value is None:
        return None
    property_name = _coerce_css_property_name(value)
    return property_name or None


def _coerce_property_classification(
    value: PropertyClassification | str | None,
) -> PropertyClassification:
    if isinstance(value, PropertyClassification):
        return value
    normalized = str(value or PropertyClassification.OTHER.value).strip().lower()
    try:
        return PropertyClassification(normalized or PropertyClassification.OTHER.value)
    except ValueError:
        return PropertyClassification.OTHER


def classify_property(property_name: str) -> PropertyClassification:
    normalized_name = _normalize_property_name(property_name)
    property_data = _property_data(normalized_name)
    if normalized_name in _EFFECT_COLOR_PROPERTIES:
        return PropertyClassification.EFFECT
    if property_data is None:
        return PropertyClassification.OTHER
    if property_data[ROLE] == Role.BACKGROUND:
        return PropertyClassification.BACKGROUND
    if property_data[ROLE] == Role.FOREGROUND:
        return PropertyClassification.FOREGROUND
    return PropertyClassification.OTHER


def classify_element(properties: tuple["Property", ...]) -> PropertyClassification:
    seen = {property_model.classification for property_model in properties}
    for candidate in (
        PropertyClassification.BACKGROUND,
        PropertyClassification.FOREGROUND,
        PropertyClassification.EFFECT,
        PropertyClassification.OTHER,
    ):
        if candidate in seen:
            return candidate
    return PropertyClassification.OTHER


@dataclass(slots=True)
class Property:
    name: str
    value: str
    classification: PropertyClassification = PropertyClassification.OTHER
    color_id: str | None = None
    color_ids: tuple[str, ...] = field(default_factory=tuple)
    style_id: str | None = None
    declaration_id: str | None = None
    declared_property: str | None = None
    inherited_from_element_id: str | None = None
    token_ids: tuple[str, ...] = field(default_factory=tuple)
    applied_token_id: str | None = None
    token_alias_to: str | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        name = _coerce_css_property_name(payload.get("name"))
        value = str(payload.get("value") or "")
        raw_classification = payload.get("classification")
        return cls(
            name=name,
            value=value,
            classification=(
                _coerce_property_classification(raw_classification)
                if raw_classification
                else classify_property(name)
            ),
            color_id=str(payload["color_id"]) if payload.get("color_id") is not None else None,
            color_ids=(
                tuple(
                    str(item).strip()
                    for item in (payload.get("color_ids") or ())
                    if str(item).strip()
                )
                or (
                    (str(payload["color_id"]).strip(),)
                    if payload.get("color_id") is not None and str(payload["color_id"]).strip()
                    else ()
                )
            ),
            style_id=str(payload["style_id"]) if payload.get("style_id") is not None else None,
            declaration_id=(
                str(payload["declaration_id"])
                if payload.get("declaration_id") is not None
                else None
            ),
            declared_property=(
                _coerce_optional_css_property_name(payload["declared_property"])
                if payload.get("declared_property") is not None
                else None
            ),
            inherited_from_element_id=(
                str(payload["inherited_from_element_id"])
                if payload.get("inherited_from_element_id") is not None
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
        computed_style: Mapping[str, Any],
        color_id: str | None = None,
        classification: PropertyClassification | str | None = None,
    ) -> Self:
        normalized_name = _coerce_css_property_name(name)
        return cls(
            name=normalized_name,
            value=str(computed_style.get("computed_value") or ""),
            classification=(
                _coerce_property_classification(classification)
                if classification
                else classify_property(normalized_name)
            ),
            color_id=color_id,
            style_id=(
                str(computed_style["style_id"])
                if computed_style.get("style_id") is not None
                else None
            ),
            declaration_id=(
                str(computed_style["declaration_id"])
                if computed_style.get("declaration_id") is not None
                else None
            ),
            declared_property=(
                _coerce_optional_css_property_name(computed_style["declared_property"])
                if computed_style.get("declared_property") is not None
                else None
            ),
            inherited_from_element_id=(
                str(computed_style["inherited_from_element_id"])
                if computed_style.get("inherited_from_element_id") is not None
                else None
            ),
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
        return replace(
            self,
            token_ids=tuple(dict.fromkeys((*self.token_ids, normalized_token_id)).keys()),
            applied_token_id=normalized_token_id if applied else self.applied_token_id,
            token_alias_to=alias_to if alias_to is not None else self.token_alias_to,
        )

    def set_color_id(self, color_id: str | None) -> Self:
        normalized = str(color_id or "").strip()
        self.color_id = normalized or None
        self.color_ids = (normalized,) if normalized else ()
        return self

    def set_color_ids(self, color_ids: Iterable[str]) -> Self:
        ordered = tuple(
            dict.fromkeys(
                str(item).strip()
                for item in color_ids
                if str(item).strip()
            )
        )
        self.color_ids = ordered
        self.color_id = ordered[0] if len(ordered) == 1 else None
        return self

    @property
    def property_id(self) -> str | None:
        property_name = _normalize_property_name(self.name)
        return property_name if property_name in CSS_PROPERTIES else None

    def color_values(self) -> tuple[str, ...]:
        property_id = self.property_id
        if property_id is None:
            return ()
        if property_id not in _COLOR_VALUE_PROPERTIES and property_id not in _EFFECT_COLOR_PROPERTIES:
            return ()

        if property_id in _PURE_COLOR_PROPERTIES:
            normalized = color_registry.normalize_css_color_token(self.value)
            return () if not normalized or normalized == "transparent" else (normalized,)

        colors: list[str] = []
        for token in _HEX_COLOR_RE.findall(self.value):
            normalized = color_registry.normalize_css_color_token(token)
            if normalized and normalized != "transparent" and normalized not in colors:
                colors.append(normalized)
        for token in _FUNCTION_COLOR_RE.findall(self.value):
            normalized = color_registry.normalize_css_color_token(token)
            if normalized and normalized != "transparent" and normalized not in colors:
                colors.append(normalized)
        return tuple(colors)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "classification": self.classification.value,
        }
        if self.color_id is not None:
            payload["color_id"] = self.color_id
        if self.color_ids:
            payload["color_ids"] = list(self.color_ids)
        if self.style_id is not None:
            payload["style_id"] = self.style_id
        if self.declaration_id is not None:
            payload["declaration_id"] = self.declaration_id
        if self.declared_property is not None:
            payload["declared_property"] = self.declared_property
        if self.inherited_from_element_id is not None:
            payload["inherited_from_element_id"] = self.inherited_from_element_id
        if self.token_ids:
            payload["token_ids"] = list(self.token_ids)
        if self.applied_token_id is not None:
            payload["applied_token_id"] = self.applied_token_id
        if self.token_alias_to is not None:
            payload["token_alias_to"] = self.token_alias_to
        return payload


def _origin_family(candidate: Mapping[str, Any]) -> str:
    source_kind = str(candidate.get("source_kind") or "").strip().lower()
    origin = str(candidate.get("origin") or "").strip().lower()
    if source_kind in {"inline", "embedded", "external", "inherited"}:
        return "author"
    if origin == "user":
        return "user"
    if origin == "user-agent" or source_kind == "user-agent":
        return "user-agent"
    return "author"


def _inline_specificity(candidate: Mapping[str, Any]) -> tuple[int, int, int, int]:
    if str(candidate.get("source_kind") or "").strip().lower() == "inline":
        return (1, 0, 0, 0)
    specificity = candidate.get("specificity")
    if isinstance(specificity, tuple):
        return (0, specificity[0], specificity[1], specificity[2])
    if isinstance(specificity, list) and len(specificity) >= 3:
        return (0, int(specificity[0]), int(specificity[1]), int(specificity[2]))
    return (0, 0, 0, 0)


def _layer_priority(candidate: Mapping[str, Any]) -> tuple[int, int]:
    layer_order = candidate.get("layer_order")
    source_kind = str(candidate.get("source_kind") or "").strip().lower()
    inline_bonus = 2 if source_kind == "inline" else 0

    if bool(candidate.get("important")):
        if source_kind == "inline":
            return (inline_bonus, 0)
        if layer_order is None:
            return (0, 0)
        return (1, -int(layer_order))

    if source_kind == "inline":
        return (inline_bonus, 0)
    if layer_order is None:
        return (1, 0)
    return (0, int(layer_order))


def _cascade_sort_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    important = 1 if bool(candidate.get("important")) else 0
    origin_family = _origin_family(candidate)
    if important:
        origin_rank = {"author": 0, "user": 1, "user-agent": 2}.get(origin_family, 0)
    else:
        origin_rank = {"user-agent": 0, "user": 1, "author": 2}.get(origin_family, 2)
    return (
        important,
        origin_rank,
        _layer_priority(candidate),
        _inline_specificity(candidate),
        candidate.get("source_order"),
    )


def resolve_property_winner(
    *,
    computed_value: str,
    candidates: Iterable[Mapping[str, Any]],
    mark_selector_used: Callable[[str, str | None], None] | None = None,
) -> dict[str, Any]:
    candidate_pool = tuple(candidates)
    direct_candidates = tuple(
        candidate for candidate in candidate_pool if not candidate.get("inherited_from_element_id")
    )
    ranked_candidates = sorted(direct_candidates or candidate_pool, key=_cascade_sort_key)
    if not ranked_candidates:
        return {"computed_value": computed_value}

    winner = ranked_candidates[-1]
    if len(ranked_candidates) > 1 and _cascade_sort_key(ranked_candidates[-1]) == _cascade_sort_key(ranked_candidates[-2]):
        return {"computed_value": computed_value}

    style_id = str(winner.get("style_id") or "").strip()
    selector_id = str(winner.get("selector_id") or "").strip() or None
    if mark_selector_used is not None and style_id:
        mark_selector_used(style_id, selector_id)

    payload: dict[str, Any] = {
        "computed_value": computed_value,
    }
    for key in ("style_id", "declaration_id", "declared_property", "inherited_from_element_id"):
        value = winner.get(key)
        if value not in (None, ""):
            payload[key] = value
    return payload


def resolve_element_computed_styles(
    *,
    computed_styles: Mapping[str, str],
    candidates_by_property: Mapping[str, Iterable[Mapping[str, Any]]],
    mark_selector_used: Callable[[str, str | None], None] | None = None,
) -> dict[str, dict[str, Any]]:
    resolved: dict[str, dict[str, Any]] = {}
    for property_name, computed_value in computed_styles.items():
        resolved[property_name] = resolve_property_winner(
            computed_value=computed_value,
            candidates=candidates_by_property.get(property_name, ()),
            mark_selector_used=mark_selector_used,
        )
    return resolved


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
            tag_name=str(payload.get("tag_name") or "").strip(),
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
