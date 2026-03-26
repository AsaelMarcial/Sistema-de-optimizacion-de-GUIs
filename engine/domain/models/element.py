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

    def to_artifact_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.id is not None:
            payload["id"] = self.id
        if self.name is not None:
            payload["name"] = self.name
        if self.role is not None:
            payload["role"] = self.role
        if self.class_list:
            payload["class_list"] = list(self.class_list)
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

    def to_artifact_dict(self) -> dict[str, bool]:
        payload: dict[str, bool] = {}
        if self.is_out_of_scope:
            payload["is_out_of_scope"] = True
        if self.is_visible:
            payload["is_visible"] = True
        if self.is_stacking_context:
            payload["is_stacking_context"] = True
        if self.is_text_node:
            payload["is_text_node"] = True
        if self.is_leaf:
            payload["is_leaf"] = True
        if self.has_siblings:
            payload["has_siblings"] = True
        return payload


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
        styles_payload = payload.get("styles") or {}
        if not styles_payload and payload.get("effective_background") is not None:
            effective_background_payload = payload.get("effective_background")
            if isinstance(effective_background_payload, Mapping):
                styles_payload = {
                    "effective_background": (
                        effective_background_payload.get("value")
                        or effective_background_payload.get("effective_background")
                        or effective_background_payload.get("css")
                    ),
                    "effective_background_color_id": (
                        effective_background_payload.get("color_id")
                        or effective_background_payload.get("effective_background_color_id")
                    ),
                }
            else:
                styles_payload = {
                    "effective_background": effective_background_payload,
                    "effective_background_color_id": payload.get("effective_background_color_id"),
                }

        computed_styles_payload = dict(payload.get("computed_styles") or {})
        color_properties_payload = tuple(payload.get("color_properties") or ())
        if not computed_styles_payload and not color_properties_payload and payload.get("properties"):
            computed_styles_payload = {}
            color_properties_list: list[dict[str, Any]] = []
            for property_payload in payload.get("properties") or ():
                if not isinstance(property_payload, Mapping):
                    continue
                property_name = str(
                    property_payload.get("name") or property_payload.get("property_name") or ""
                ).strip()
                computed_value = property_payload.get("value")
                if computed_value in (None, ""):
                    computed_value = property_payload.get("computed_value")
                if computed_value in (None, ""):
                    computed_value = property_payload.get("resolved_value")
                if not property_name or computed_value in (None, ""):
                    continue

                computed_payload: dict[str, Any] = {
                    "computed_value": str(computed_value),
                }
                if property_payload.get("style_id") is not None:
                    computed_payload["style_id"] = property_payload.get("style_id")
                if property_payload.get("kind") is not None:
                    computed_payload["kind"] = property_payload.get("kind")
                if property_payload.get("declared_property") is not None:
                    computed_payload["declared_property"] = property_payload.get("declared_property")
                if property_payload.get("declaration_id") is not None:
                    computed_payload["declaration_id"] = property_payload.get("declaration_id")
                if property_payload.get("inherited_from_element_id") is not None:
                    computed_payload["inherited_from_element_id"] = property_payload.get(
                        "inherited_from_element_id"
                    )
                if property_payload.get("resolution_status") is not None:
                    computed_payload["resolution_status"] = property_payload.get("resolution_status")
                elif property_payload.get("status") is not None:
                    computed_payload["resolution_status"] = property_payload.get("status")
                computed_styles_payload[property_name] = computed_payload

                if any(
                    property_payload.get(key) is not None
                    for key in ("color_id", "color_property_id", "source_kind")
                ):
                    color_properties_list.append(
                        {
                            "color_property_id": (
                                property_payload.get("color_property_id")
                                or f"{payload.get('node_id') or ''}:{property_name}"
                            ),
                            "property_name": property_name,
                            "source_kind": property_payload.get("source_kind") or "own",
                            "resolved_value": str(computed_value),
                            "status": (
                                property_payload.get("status")
                                or property_payload.get("resolution_status")
                                or "kept"
                            ),
                            "color_id": property_payload.get("color_id"),
                            "winning_style_ref": {
                                "style_id": property_payload.get("style_id"),
                                "declaration_id": property_payload.get("declaration_id"),
                                "declared_property": property_payload.get("declared_property"),
                                "inherited_from_element_id": property_payload.get(
                                    "inherited_from_element_id"
                                ),
                            },
                        }
                    )
            color_properties_payload = tuple(color_properties_list)

        return cls(
            node_id=str(payload.get("node_id") or ""),
            backend_node_id=int(payload.get("backend_node_id") or 0),
            document_order=int(payload.get("document_order") or 0),
            identity=ElementIdentityModel.build(payload.get("identity") or {}),
            layout=ElementLayoutModel.build(payload.get("layout") or {}),
            styles=ElementStyleStateModel.build(styles_payload),
            computed_styles={
                str(property_name): (
                    style_payload
                    if isinstance(style_payload, ComputedStyleValueModel)
                    else ComputedStyleValueModel.build(style_payload)
                )
                for property_name, style_payload in computed_styles_payload.items()
                if isinstance(style_payload, (ComputedStyleValueModel, Mapping))
            },
            color_properties=tuple(
                color_property
                if isinstance(color_property, ElementColorPropertyModel)
                else ElementColorPropertyModel.build(color_property)
                for color_property in color_properties_payload
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

    def _property_payloads(self) -> list[dict[str, Any]]:
        properties_by_name: dict[str, dict[str, Any]] = {}

        for property_name, computed_style in sorted(self.computed_styles.items()):
            property_payload: dict[str, Any] = {
                "name": property_name,
                "value": computed_style.computed_value,
            }
            if computed_style.style_id is not None:
                property_payload["style_id"] = computed_style.style_id
            if computed_style.kind is not None:
                property_payload["kind"] = computed_style.kind.value
            if computed_style.declared_property is not None:
                property_payload["declared_property"] = computed_style.declared_property
            if computed_style.declaration_id is not None:
                property_payload["declaration_id"] = computed_style.declaration_id
            if computed_style.inherited_from_element_id is not None:
                property_payload["inherited_from_element_id"] = computed_style.inherited_from_element_id
            if computed_style.resolution_status is not None:
                property_payload["resolution_status"] = computed_style.resolution_status.value
            properties_by_name[property_name] = property_payload

        for color_property in self.color_properties:
            property_payload = properties_by_name.setdefault(
                color_property.property_name,
                {
                    "name": color_property.property_name,
                    "value": color_property.resolved_value,
                },
            )
            property_payload["color_property_id"] = color_property.color_property_id
            property_payload["color_id"] = color_property.color_id
            if color_property.source_kind.value != "own":
                property_payload["source_kind"] = color_property.source_kind.value
            winning_style_ref = color_property.winning_style_ref
            if winning_style_ref.style_id is not None and "style_id" not in property_payload:
                property_payload["style_id"] = winning_style_ref.style_id
            if (
                winning_style_ref.declaration_id is not None
                and "declaration_id" not in property_payload
            ):
                property_payload["declaration_id"] = winning_style_ref.declaration_id
            if (
                winning_style_ref.declared_property is not None
                and "declared_property" not in property_payload
            ):
                property_payload["declared_property"] = winning_style_ref.declared_property
            if (
                winning_style_ref.inherited_from_element_id is not None
                and "inherited_from_element_id" not in property_payload
            ):
                property_payload["inherited_from_element_id"] = (
                    winning_style_ref.inherited_from_element_id
                )

        return [properties_by_name[name] for name in sorted(properties_by_name)]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "node_id": self.node_id,
            "backend_node_id": self.backend_node_id,
            "document_order": self.document_order,
            "identity": self.identity.to_artifact_dict(),
            "layout": self.layout.to_dict(),
        }
        if property_payloads := self._property_payloads():
            payload["properties"] = property_payloads
        if self.styles.effective_background is not None or self.styles.effective_background_color_id is not None:
            effective_background: dict[str, Any] = {}
            if self.styles.effective_background is not None:
                effective_background["value"] = self.styles.effective_background
            if self.styles.effective_background_color_id is not None:
                effective_background["color_id"] = self.styles.effective_background_color_id
            payload["effective_background"] = effective_background
        if flags_payload := self.flags.to_artifact_dict():
            payload["flags"] = flags_payload
        if self.text is not None:
            payload["text"] = self.text
        if self.parent_id is not None:
            payload["parent_id"] = self.parent_id
        if self.children_ids:
            payload["children_ids"] = list(self.children_ids)
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
