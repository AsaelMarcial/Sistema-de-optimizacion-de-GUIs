from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
import re
from typing import Any, Iterator, Mapping, Self

from engine.adapters.color_service import color_registry
from engine.domain.data.css_properties import CSS_PROPERTIES_BY_ID
from engine.domain.models.color import ColorInventoryEntry, ColorInventoryModel
from engine.domain.models.element import Element, Property, classify_property
from engine.domain.models.style import StyleInventoryModel

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
    }
)
_PURE_COLOR_PROPERTIES = frozenset(
    property_name
    for property_name, spec in CSS_PROPERTIES_BY_ID.items()
    if spec.color_role is not None and property_name not in _COMPOSITE_COLOR_PROPERTIES
)
_COLOR_VALUE_PROPERTIES = _PURE_COLOR_PROPERTIES | _COMPOSITE_COLOR_PROPERTIES
_CSS_OVERVIEW_COLOR_ROLES = ("text", "background", "border", "fill", "stroke")


def _normalize_color_token(value: str) -> str:
    return color_registry.normalize_css_color_token(value)


def _extract_palette_colors(property_name: str, value: str) -> tuple[str, ...]:
    if property_name not in _COLOR_VALUE_PROPERTIES:
        return ()

    if property_name in _PURE_COLOR_PROPERTIES:
        normalized = _normalize_color_token(value)
        return () if not normalized or normalized == "transparent" else (normalized,)

    colors: list[str] = []
    for token in _HEX_COLOR_RE.findall(value):
        normalized = _normalize_color_token(token)
        if normalized and normalized != "transparent" and normalized not in colors:
            colors.append(normalized)
    for token in _FUNCTION_COLOR_RE.findall(value):
        normalized = _normalize_color_token(token)
        if normalized and normalized != "transparent" and normalized not in colors:
            colors.append(normalized)
    return tuple(colors)


def build_observed_color_payloads(
    css_overview: Mapping[str, Any] | None,
    *,
    existing_inventory: ColorInventoryModel | None = None,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    colors_by_role = dict((css_overview or {}).get("colors") or {})
    for role in _CSS_OVERVIEW_COLOR_ROLES:
        for entry in colors_by_role.get(role) or ():
            value = str(entry.get("css") or entry.get("hex") or "").strip()
            if not value:
                continue
            node_ids = tuple(
                str(item).strip()
                for item in (entry.get("node_ids") or ())
                if str(item).strip()
            )
            count = int(entry.get("count") or len(node_ids) or 0)
            payload: dict[str, Any] = {
                "value": value,
                "usage_count": len(node_ids) or count,
                "node_ids": list(node_ids),
                "observed_usage_count": len(node_ids) or count,
                "observed_roles": [
                    {
                        "role": role,
                        "count": count,
                        "node_ids": list(node_ids),
                        "sample_selectors": [
                            str(item).strip()
                            for item in (entry.get("sample_selectors") or ())
                            if str(item).strip()
                        ],
                    }
                ],
                "declared_in_snapshot": False,
            }
            if existing_inventory is not None:
                existing_entry = existing_inventory.entry_by_value(value)
                if existing_entry is not None:
                    payload["color_id"] = existing_entry.color_id
            payloads.append(payload)
    return payloads


@dataclass(frozen=True, slots=True)
class PrototypeIndexes:
    by_tag: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    by_classification: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    by_depth: Mapping[int, tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "by_tag": {key: list(value) for key, value in self.by_tag.items()},
            "by_classification": {key: list(value) for key, value in self.by_classification.items()},
            "by_depth": {str(key): list(value) for key, value in self.by_depth.items()},
        }


@dataclass(frozen=True, slots=True)
class PrototypeStructure:
    nodes: tuple[Element, ...] = field(default_factory=tuple)
    indexes: PrototypeIndexes = field(default_factory=PrototypeIndexes)
    declaration_values: Mapping[str, str] = field(default_factory=dict)
    _node_by_id: Mapping[str, Element] = field(default_factory=dict, repr=False, compare=False)
    _children_by_id: Mapping[str, tuple[Element, ...]] = field(default_factory=dict, repr=False, compare=False)
    _depth_by_id: Mapping[str, int] = field(default_factory=dict, repr=False, compare=False)

    @classmethod
    def build(
        cls,
        payload: Any,
        *,
        styles_inventory: StyleInventoryModel | None = None,
        declaration_values: Mapping[str, str] | None = None,
    ) -> Self:
        if isinstance(payload, cls):
            return payload
        if isinstance(payload, Mapping):
            nodes_payload = payload.get("nodes") or ()
        else:
            nodes_payload = payload
        nodes = tuple(
            node if isinstance(node, Element) else Element.build(node)
            for node in (nodes_payload or ())
        )
        declaration_lookup = dict(declaration_values or {})
        if styles_inventory is not None:
            declaration_lookup.update(_build_declaration_value_lookup(styles_inventory))
        normalized_nodes = _normalize_nodes(nodes, declaration_lookup)
        node_by_id = {node.node_id: node for node in normalized_nodes}
        children_by_id = _build_children_lookup(normalized_nodes, node_by_id)
        depth_by_id = _build_depths(normalized_nodes, node_by_id)
        return cls(
            nodes=normalized_nodes,
            indexes=_build_indexes(normalized_nodes, depth_by_id),
            declaration_values=declaration_lookup,
            _node_by_id=node_by_id,
            _children_by_id=children_by_id,
            _depth_by_id=depth_by_id,
        )

    def __iter__(self) -> Iterator[Element]:
        return iter(self.nodes)

    def __len__(self) -> int:
        return len(self.nodes)

    def node_by_id(self, node_id: str) -> Element | None:
        return self._node_by_id.get(str(node_id or "").strip())

    def parent_of(self, node_id: str) -> Element | None:
        entry = self.node_by_id(node_id)
        if entry is None or entry.parent_id is None:
            return None
        return self.node_by_id(entry.parent_id)

    def children_of(self, node_id: str) -> tuple[Element, ...]:
        return self._children_by_id.get(str(node_id or "").strip(), ())

    def ancestors_of(self, node_id: str) -> tuple[Element, ...]:
        ancestors: list[Element] = []
        current = self.parent_of(node_id)
        while current is not None:
            ancestors.append(current)
            current = self.parent_of(current.node_id)
        return tuple(ancestors)

    def descendants_of(self, node_id: str) -> tuple[Element, ...]:
        descendants: list[Element] = []
        for child in self.children_of(node_id):
            descendants.append(child)
            descendants.extend(self.descendants_of(child.node_id))
        return tuple(descendants)

    def properties_for(self, node: str | Element) -> tuple[Property, ...]:
        entry = self.node_by_id(node) if isinstance(node, str) else node
        if entry is None:
            return ()
        return entry.properties

    def visible_nodes(self) -> tuple[Element, ...]:
        return tuple(node for node in self.nodes if node.is_visible)

    def root_nodes(self) -> tuple[Element, ...]:
        return tuple(node for node in self.nodes if node.parent_id is None)

    def effective_background_of(
        self,
        node_id: str,
        colors_inventory: ColorInventoryModel,
    ) -> ColorInventoryEntry | None:
        entry = self.node_by_id(node_id)
        if entry is None:
            return None
        if entry.effective_background:
            background = colors_inventory.entry_by_value(entry.effective_background)
            if background is not None:
                return background
        for candidate in (entry, *self.ancestors_of(node_id)):
            for property_model in candidate.properties:
                if property_model.classification != "background" or not property_model.color_id:
                    continue
                color_entry = colors_inventory.entry_by_id(property_model.color_id)
                if color_entry is not None:
                    return color_entry
        return None

    def effective_color_of(
        self,
        node_id: str,
        colors_inventory: ColorInventoryModel,
    ) -> ColorInventoryEntry | None:
        entry = self.node_by_id(node_id)
        if entry is None:
            return None
        for candidate in (entry, *self.ancestors_of(node_id)):
            for property_model in candidate.properties:
                if property_model.name != "color" or not property_model.color_id:
                    continue
                color_entry = colors_inventory.entry_by_id(property_model.color_id)
                if color_entry is not None:
                    return color_entry
        return None

    def surface_container_of(self, node_id: str) -> Element | None:
        entry = self.node_by_id(node_id)
        if entry is None:
            return None
        for candidate in (entry, *self.ancestors_of(node_id)):
            has_background = any(
                property_model.classification == "background" and property_model.color_id
                for property_model in candidate.properties
            )
            if has_background:
                return candidate
        return None

    def build_color_inventory(
        self,
        *,
        css_overview: Mapping[str, Any] | None = None,
        existing_inventory: ColorInventoryModel | None = None,
    ) -> ColorInventoryModel:
        payloads: list[dict[str, Any]] = []
        for entry in self.nodes:
            seen_signatures: set[tuple[str, str]] = set()
            for property_model in entry.properties:
                for color_value in _extract_palette_colors(property_model.name, property_model.value):
                    signature = (property_model.name, color_value)
                    if signature in seen_signatures:
                        continue
                    seen_signatures.add(signature)
                    existing_entry = (
                        existing_inventory.entry_by_value(color_value)
                        if existing_inventory is not None
                        else None
                    )
                    payload: dict[str, Any] = {
                        "value": color_value,
                        "usage_count": 1,
                        "node_ids": [entry.node_id],
                        "usage": [
                            {
                                "tag": entry.tag_name,
                                "property": property_model.name,
                                "count": 1,
                            }
                        ],
                    }
                    preserved_entry = existing_entry
                    if property_model.color_id is not None and existing_inventory is not None:
                        preserved_entry = (
                            existing_inventory.entry_by_id(property_model.color_id)
                            or existing_entry
                        )
                    if property_model.color_id is not None:
                        payload["color_id"] = property_model.color_id
                    elif preserved_entry is not None:
                        payload["color_id"] = preserved_entry.color_id
                    payloads.append(payload)

        payloads.extend(
            build_observed_color_payloads(
                css_overview,
                existing_inventory=existing_inventory,
            )
        )
        inventory = ColorInventoryModel.build(payloads)
        if existing_inventory is None:
            return inventory

        merged_entries: list[ColorInventoryEntry] = []
        for entry in inventory:
            existing_entry = existing_inventory.entry_by_id(entry.color_id) or existing_inventory.entry_by_value(
                entry.value
            )
            if existing_entry is None:
                merged_entries.append(entry)
                continue
            merged_entries.append(
                replace(
                    entry,
                    display_pixel_count=existing_entry.display_pixel_count,
                    display_pixel_percentage=existing_entry.display_pixel_percentage,
                    clustered_from_display_pixels=existing_entry.clustered_from_display_pixels,
                    mapped_palette_id=existing_entry.mapped_palette_id,
                    mapped_tone=existing_entry.mapped_tone,
                    mapped_tone_rgb=existing_entry.mapped_tone_rgb,
                    mapped_tone_distance=existing_entry.mapped_tone_distance,
                )
            )
        return ColorInventoryModel.build(merged_entries)

    def to_tree(self) -> list[dict[str, Any]]:
        def _visit(node: Element) -> dict[str, Any]:
            payload = node.to_dict()
            children = self.children_of(node.node_id)
            if children:
                payload["children"] = [_visit(child) for child in children]
            return payload

        return [_visit(node) for node in self.root_nodes()]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": [node.to_dict() for node in self.nodes],
            "indexes": self.indexes.to_dict(),
        }


def _build_declaration_value_lookup(
    styles_inventory: StyleInventoryModel,
) -> dict[str, str]:
    return {
        declaration.declaration_id: declaration.value
        for style_entry in styles_inventory
        for declaration in style_entry.declarations
        if declaration.declaration_id and str(declaration.value or "").strip()
    }


def _normalize_nodes(
    nodes: tuple[Element, ...],
    declaration_lookup: Mapping[str, str],
) -> tuple[Element, ...]:
    normalized_nodes: list[Element] = []
    for entry in nodes:
        properties: list[Property] = []
        for property_model in entry.properties:
            authored_value = property_model.authored_value
            declaration_id = str(property_model.declaration_id or "").strip()
            if authored_value is None and declaration_id and declaration_id in declaration_lookup:
                authored_value = declaration_lookup[declaration_id]
            properties.append(
                replace(
                    property_model,
                    classification=property_model.classification or classify_property(property_model.name),
                    authored_value=authored_value,
                )
            )
        normalized_nodes.append(replace(entry, properties=tuple(properties)))
    return tuple(normalized_nodes)


def _build_children_lookup(
    nodes: tuple[Element, ...],
    node_by_id: Mapping[str, Element],
) -> dict[str, tuple[Element, ...]]:
    children_by_id: dict[str, list[Element]] = defaultdict(list)
    for node in nodes:
        if node.parent_id:
            parent = node_by_id.get(node.parent_id)
            if parent is not None:
                children_by_id[parent.node_id].append(node)
    return {
        node_id: tuple(sorted(children, key=lambda item: (item.document_order, item.node_id)))
        for node_id, children in children_by_id.items()
    }


def _build_depths(
    nodes: tuple[Element, ...],
    node_by_id: Mapping[str, Element],
) -> dict[str, int]:
    depths: dict[str, int] = {}

    def _depth(node_id: str) -> int:
        if node_id in depths:
            return depths[node_id]
        entry = node_by_id.get(node_id)
        if entry is None or entry.parent_id is None:
            depths[node_id] = 0
            return 0
        parent_depth = _depth(entry.parent_id)
        depths[node_id] = parent_depth + 1
        return depths[node_id]

    for entry in nodes:
        _depth(entry.node_id)
    return depths


def _build_indexes(
    nodes: tuple[Element, ...],
    depth_by_id: Mapping[str, int],
) -> PrototypeIndexes:
    by_tag: dict[str, list[str]] = defaultdict(list)
    by_classification: dict[str, list[str]] = defaultdict(list)
    by_depth: dict[int, list[str]] = defaultdict(list)

    for entry in nodes:
        by_tag[entry.tag_name].append(entry.node_id)
        by_depth[depth_by_id.get(entry.node_id, 0)].append(entry.node_id)
        seen_classifications = {property_model.classification for property_model in entry.properties}
        for classification in sorted(seen_classifications):
            by_classification[classification].append(entry.node_id)

    return PrototypeIndexes(
        by_tag={key: tuple(value) for key, value in sorted(by_tag.items())},
        by_classification={key: tuple(value) for key, value in sorted(by_classification.items())},
        by_depth={key: tuple(value) for key, value in sorted(by_depth.items())},
    )
