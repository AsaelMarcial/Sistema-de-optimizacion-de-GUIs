from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterator, Mapping, Self

from engine.domain.enums.types.elements import ElementSourceKind
from engine.domain.enums.types.style import StyleResolutionStatus
from engine.domain.models.style import ComputedStyleValueModel


def _coerce_element_source_kind(
    value: ElementSourceKind | str | None,
) -> ElementSourceKind:
    if isinstance(value, ElementSourceKind):
        return value
    normalized = str(value or ElementSourceKind.OWN.value).strip().lower()
    return ElementSourceKind(normalized)


@dataclass(frozen=True, slots=True)
class ElementAbsoluteBoundsModel:
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            left=float(payload.get("left") or 0.0),
            top=float(payload.get("top") or 0.0),
            right=float(payload.get("right") or 0.0),
            bottom=float(payload.get("bottom") or 0.0),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "left": self.left,
            "top": self.top,
            "right": self.right,
            "bottom": self.bottom,
        }


@dataclass(frozen=True, slots=True)
class ElementLayoutModel:
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    absolute_bounds: ElementAbsoluteBoundsModel = field(default_factory=ElementAbsoluteBoundsModel)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            x=float(payload.get("x") or 0.0),
            y=float(payload.get("y") or 0.0),
            width=float(payload.get("width") or 0.0),
            height=float(payload.get("height") or 0.0),
            absolute_bounds=ElementAbsoluteBoundsModel.build(payload.get("absolute_bounds") or {}),
        )

    def area(self) -> float:
        return self.width * self.height

    def to_dict(self) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "absolute_bounds": self.absolute_bounds.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ElementIdentityModel:
    tag: str
    node_name: str
    id: str | None = None
    name: str | None = None
    role: str | None = None
    class_list: tuple[str, ...] = field(default_factory=tuple)
    data_attributes: dict[str, str] = field(default_factory=dict)
    attributes: dict[str, str] = field(default_factory=dict)
    selector_hint: str | None = None
    xpath: str | None = None
    related_media: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            tag=str(payload.get("tag") or ""),
            node_name=str(payload.get("node_name") or ""),
            id=str(payload["id"]) if payload.get("id") is not None else None,
            name=str(payload["name"]) if payload.get("name") is not None else None,
            role=str(payload["role"]) if payload.get("role") is not None else None,
            class_list=tuple(str(item) for item in (payload.get("class_list") or ())),
            data_attributes={
                str(key): str(value)
                for key, value in dict(payload.get("data_attributes") or {}).items()
            },
            attributes={
                str(key): str(value)
                for key, value in dict(payload.get("attributes") or {}).items()
            },
            selector_hint=(
                str(payload["selector_hint"])
                if payload.get("selector_hint") is not None
                else None
            ),
            xpath=str(payload["xpath"]) if payload.get("xpath") is not None else None,
            related_media=dict(payload.get("related_media") or {}),
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self.class_list)

    def primary_identifier(self) -> str:
        return self.id or self.name or self.xpath or self.tag

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "tag": self.tag,
            "node_name": self.node_name,
        }
        if self.id is not None:
            payload["id"] = self.id
        if self.name is not None:
            payload["name"] = self.name
        if self.role is not None:
            payload["role"] = self.role
        if self.class_list:
            payload["class_list"] = list(self.class_list)
        if self.data_attributes:
            payload["data_attributes"] = dict(self.data_attributes)
        if self.attributes:
            payload["attributes"] = dict(self.attributes)
        if self.selector_hint is not None:
            payload["selector_hint"] = self.selector_hint
        if self.xpath is not None:
            payload["xpath"] = self.xpath
        if self.related_media:
            payload["related_media"] = dict(self.related_media)
        return payload


@dataclass(frozen=True, slots=True)
class ElementWinningStyleReferenceModel:
    style_id: str | None = None
    declaration_id: str | None = None
    declared_property: str | None = None
    inherited_from_element_id: str | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
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
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.style_id is not None:
            payload["style_id"] = self.style_id
        if self.declaration_id is not None:
            payload["declaration_id"] = self.declaration_id
        if self.declared_property is not None:
            payload["declared_property"] = self.declared_property
        if self.inherited_from_element_id is not None:
            payload["inherited_from_element_id"] = self.inherited_from_element_id
        return payload


@dataclass(frozen=True, slots=True)
class ElementColorValueModel:
    value: str
    color_id: str | None = None
    token: str | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            value=str(payload.get("value") or payload.get("resolved_value") or ""),
            color_id=str(payload["color_id"]) if payload.get("color_id") is not None else None,
            token=str(payload["token"]) if payload.get("token") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"value": self.value}
        if self.color_id is not None:
            payload["color_id"] = self.color_id
        if self.token is not None:
            payload["token"] = self.token
        return payload


@dataclass(frozen=True, slots=True)
class ElementColorPropertyModel:
    color_property_id: str
    property_name: str
    source_kind: ElementSourceKind
    resolved_value: str
    status: str = "kept"
    color_id: str | None = None
    winning_style_ref: ElementWinningStyleReferenceModel = field(
        default_factory=ElementWinningStyleReferenceModel
    )
    before: ElementColorValueModel | None = None
    after: ElementColorValueModel | None = None
    annotations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_kind",
            _coerce_element_source_kind(self.source_kind),
        )

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        before_payload = payload.get("before") or {}
        after_payload = payload.get("after") or {}
        winning_style_payload = payload.get("winning_style_ref") or payload.get("winningStyleRef") or {}
        return cls(
            color_property_id=str(payload.get("color_property_id") or ""),
            property_name=str(payload.get("property_name") or ""),
            source_kind=_coerce_element_source_kind(payload.get("source_kind")),
            resolved_value=str(payload.get("resolved_value") or ""),
            status=str(payload.get("status") or "kept"),
            color_id=str(payload["color_id"]) if payload.get("color_id") is not None else None,
            winning_style_ref=(
                winning_style_payload
                if isinstance(winning_style_payload, ElementWinningStyleReferenceModel)
                else ElementWinningStyleReferenceModel.build(winning_style_payload)
            ),
            before=(
                before_payload
                if isinstance(before_payload, ElementColorValueModel)
                else ElementColorValueModel.build(before_payload)
            )
            if before_payload
            else None,
            after=(
                after_payload
                if isinstance(after_payload, ElementColorValueModel)
                else ElementColorValueModel.build(after_payload)
            )
            if after_payload
            else None,
            annotations=tuple(str(item) for item in (payload.get("annotations") or ())),
        )

    @classmethod
    def from_computed_style(
        cls,
        *,
        node_id: str,
        index: int,
        property_name: str,
        computed_style: ComputedStyleValueModel,
        color_id: str | None = None,
    ) -> Self:
        source_kind = (
            ElementSourceKind.INHERITED
            if computed_style.inherited_from_element_id
            else ElementSourceKind.OWN
        )
        return cls(
            color_property_id=f"{node_id}:{property_name}:{index}",
            property_name=property_name,
            source_kind=source_kind,
            resolved_value=computed_style.computed_value,
            status=(
                computed_style.resolution_status.value
                if computed_style.resolution_status is not None
                else StyleResolutionStatus.EXACT_MATCH.value
            ),
            color_id=color_id,
            winning_style_ref=ElementWinningStyleReferenceModel(
                style_id=computed_style.style_id,
                declaration_id=computed_style.declaration_id,
                declared_property=computed_style.declared_property,
                inherited_from_element_id=computed_style.inherited_from_element_id,
            ),
            before=ElementColorValueModel(
                value=computed_style.computed_value,
                color_id=color_id,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "color_property_id": self.color_property_id,
            "property_name": self.property_name,
            "source_kind": self.source_kind.value,
            "resolved_value": self.resolved_value,
            "status": self.status,
        }
        if self.color_id is not None:
            payload["color_id"] = self.color_id
        winning_style_payload = self.winning_style_ref.to_dict()
        if winning_style_payload:
            payload["winning_style_ref"] = winning_style_payload
        if self.before is not None:
            payload["before"] = self.before.to_dict()
        if self.after is not None:
            payload["after"] = self.after.to_dict()
        if self.annotations:
            payload["annotations"] = list(self.annotations)
        return payload


@dataclass(frozen=True, slots=True)
class ElementStyleStateModel:
    effective_background: str | None = None
    effective_background_color_id: str | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            effective_background=(
                str(payload["effective_background"])
                if payload.get("effective_background") is not None
                else None
            ),
            effective_background_color_id=(
                str(payload["effective_background_color_id"])
                if payload.get("effective_background_color_id") is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.effective_background is not None:
            payload["effective_background"] = self.effective_background
        if self.effective_background_color_id is not None:
            payload["effective_background_color_id"] = self.effective_background_color_id
        return payload


@dataclass(frozen=True, slots=True)
class ElementFlagsModel:
    is_out_of_scope: bool = False
    is_visible: bool = False
    is_stacking_context: bool = False
    is_text_node: bool = False
    is_leaf: bool = False
    has_siblings: bool = False

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            is_out_of_scope=bool(payload.get("is_out_of_scope", False)),
            is_visible=bool(payload.get("is_visible", False)),
            is_stacking_context=bool(payload.get("is_stacking_context", False)),
            is_text_node=bool(payload.get("is_text_node", False)),
            is_leaf=bool(payload.get("is_leaf", False)),
            has_siblings=bool(payload.get("has_siblings", False)),
        )

    def to_dict(self) -> dict[str, bool]:
        return {
            "is_out_of_scope": self.is_out_of_scope,
            "is_visible": self.is_visible,
            "is_stacking_context": self.is_stacking_context,
            "is_text_node": self.is_text_node,
            "is_leaf": self.is_leaf,
            "has_siblings": self.has_siblings,
        }


@dataclass(frozen=True, slots=True)
class ElementInventoryEntry:
    node_id: str
    backend_node_id: int
    document_order: int
    identity: ElementIdentityModel
    layout: ElementLayoutModel
    styles: ElementStyleStateModel = field(default_factory=ElementStyleStateModel)
    computed_styles: dict[str, ComputedStyleValueModel] = field(default_factory=dict)
    color_properties: tuple[ElementColorPropertyModel, ...] = field(default_factory=tuple)
    flags: ElementFlagsModel = field(default_factory=ElementFlagsModel)
    text: str | None = None
    parent_id: str | None = None
    children_ids: tuple[str, ...] = field(default_factory=tuple)
    paint_order: int | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            node_id=str(payload.get("node_id") or ""),
            backend_node_id=int(payload.get("backend_node_id") or 0),
            document_order=int(payload.get("document_order") or 0),
            identity=ElementIdentityModel.build(payload.get("identity") or {}),
            layout=ElementLayoutModel.build(payload.get("layout") or {}),
            styles=ElementStyleStateModel.build(payload.get("styles") or {}),
            computed_styles={
                str(property_name): (
                    style_payload
                    if isinstance(style_payload, ComputedStyleValueModel)
                    else ComputedStyleValueModel.build(style_payload)
                )
                for property_name, style_payload in dict(payload.get("computed_styles") or {}).items()
                if isinstance(style_payload, (ComputedStyleValueModel, Mapping))
            },
            color_properties=tuple(
                color_property
                if isinstance(color_property, ElementColorPropertyModel)
                else ElementColorPropertyModel.build(color_property)
                for color_property in (payload.get("color_properties") or ())
                if isinstance(color_property, (ElementColorPropertyModel, Mapping))
            ),
            flags=ElementFlagsModel.build(payload.get("flags") or {}),
            text=str(payload.get("text")) if payload.get("text") is not None else None,
            parent_id=str(payload.get("parent_id")) if payload.get("parent_id") is not None else None,
            children_ids=tuple(str(item) for item in (payload.get("children_ids") or ())),
            paint_order=int(payload["paint_order"]) if payload.get("paint_order") is not None else None,
        )

    def __iter__(self) -> Iterator[str]:
        return iter(self.children_ids)

    def is_root(self) -> bool:
        return self.parent_id is None

    def iter_computed_styles(self) -> Iterator[tuple[str, ComputedStyleValueModel]]:
        return iter(self.computed_styles.items())

    def iter_color_properties(self) -> Iterator[ElementColorPropertyModel]:
        return iter(self.color_properties)

    def with_color_properties(
        self,
        color_properties: tuple[ElementColorPropertyModel, ...],
        *,
        effective_background_color_id: str | None = None,
    ) -> Self:
        styles = self.styles
        if effective_background_color_id is not None:
            styles = replace(styles, effective_background_color_id=effective_background_color_id)
        return replace(self, color_properties=color_properties, styles=styles)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "node_id": self.node_id,
            "backend_node_id": self.backend_node_id,
            "document_order": self.document_order,
            "identity": self.identity.to_dict(),
            "layout": self.layout.to_dict(),
            "styles": self.styles.to_dict(),
            "computed_styles": {
                property_name: style_payload.to_dict()
                for property_name, style_payload in self.computed_styles.items()
            },
            "flags": self.flags.to_dict(),
            "children_ids": self.children_ids,
        }
        if self.color_properties:
            payload["color_properties"] = [item.to_dict() for item in self.color_properties]
        if self.text is not None:
            payload["text"] = self.text
        if self.parent_id is not None:
            payload["parent_id"] = self.parent_id
        if self.paint_order is not None:
            payload["paint_order"] = self.paint_order
        return payload


@dataclass(frozen=True, slots=True)
class ElementInventoryModel:
    entries: tuple[ElementInventoryEntry, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payloads: Any) -> Self:
        if not payloads:
            return cls()

        deduped: dict[str, ElementInventoryEntry] = {}
        for payload in payloads:
            if isinstance(payload, ElementInventoryEntry):
                entry = payload
            elif isinstance(payload, Mapping):
                entry = ElementInventoryEntry.build(payload)
            else:
                continue
            deduped[entry.node_id] = entry

        ordered_entries = tuple(
            sorted(deduped.values(), key=lambda item: (item.document_order, item.node_id))
        )
        return cls(entries=ordered_entries)

    def __iter__(self) -> Iterator[ElementInventoryEntry]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def entry_by_id(self, node_id: str) -> ElementInventoryEntry | None:
        return next((entry for entry in self.entries if entry.node_id == node_id), None)

    def roots(self) -> tuple[ElementInventoryEntry, ...]:
        return tuple(entry for entry in self.entries if entry.is_root())

    def children_of(self, node_id: str) -> tuple[ElementInventoryEntry, ...]:
        parent = self.entry_by_id(node_id)
        if parent is None:
            return ()
        children = [self.entry_by_id(child_id) for child_id in parent.children_ids]
        return tuple(child for child in children if child is not None)

    def visible_entries(self) -> tuple[ElementInventoryEntry, ...]:
        return tuple(entry for entry in self.entries if entry.flags.is_visible)

    def to_tree(self) -> tuple[dict[str, Any], ...]:
        entries_by_id = {entry.node_id: entry for entry in self.entries}

        def _build_branch(node_id: str) -> dict[str, Any]:
            node = entries_by_id[node_id]
            payload = node.to_dict()
            payload.pop("children_ids", None)
            payload.pop("parent_id", None)
            payload["children"] = [
                _build_branch(child_id)
                for child_id in node.children_ids
                if child_id in entries_by_id
            ]
            return payload

        return tuple(_build_branch(root.node_id) for root in self.roots())

    def to_dict(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]


ElementModel = ElementInventoryEntry
