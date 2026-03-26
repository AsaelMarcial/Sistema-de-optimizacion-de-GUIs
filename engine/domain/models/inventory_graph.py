from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence, Self

from engine.domain.models.color import ColorInventoryEntry, ColorInventoryModel
from engine.domain.models.element import ElementInventoryEntry, ElementInventoryModel
from engine.domain.models.palette import TonalPaletteModel
from engine.domain.models.style import StyleInventoryEntry, StyleInventoryModel
from engine.domain.models.token import TokenInventoryModel, TokenModel


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)).keys())


def _bounds_intersect(left: ElementInventoryEntry, right: ElementInventoryEntry) -> bool:
    a = left.layout.absolute_bounds
    b = right.layout.absolute_bounds
    return not (
        a.right <= b.left
        or a.left >= b.right
        or a.bottom <= b.top
        or a.top >= b.bottom
    )


def _normalize_id_map(
    payload: Mapping[str, Any] | None,
) -> dict[str, tuple[str, ...]]:
    if not payload:
        return {}

    normalized: dict[str, tuple[str, ...]] = {}
    for key, value in payload.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            continue
        items = _unique(value or ())
        if items:
            normalized[normalized_key] = items
    return normalized


def _element_index(
    elements: ElementInventoryModel,
) -> dict[str, ElementInventoryEntry]:
    return {entry.node_id: entry for entry in elements}


def _style_index(
    styles: StyleInventoryModel,
) -> dict[str, StyleInventoryEntry]:
    return {entry.style_id: entry for entry in styles}


def _color_index(
    colors: ColorInventoryModel,
) -> dict[str, ColorInventoryEntry]:
    return {entry.color_id: entry for entry in colors}


def _palette_index(
    palettes: Sequence[TonalPaletteModel],
) -> dict[str, TonalPaletteModel]:
    return {palette.palette_id: palette for palette in palettes}


def _token_index(
    tokens: TokenInventoryModel,
) -> dict[str, TokenModel]:
    return {entry.token_id: entry for entry in tokens if entry.token_id}


def _build_token_relations(
    tokens: TokenInventoryModel | None,
) -> tuple[
    tuple[str, ...],
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
    dict[str, tuple[str, ...]],
]:
    if tokens is None:
        return (), {}, {}, {}, {}

    token_ids: list[str] = []
    element_to_token_ids: dict[str, list[str]] = defaultdict(list)
    style_ref_to_token_ids: dict[str, list[str]] = defaultdict(list)
    color_to_token_ids: dict[str, list[str]] = defaultdict(list)
    palette_tone_to_token_ids: dict[str, list[str]] = defaultdict(list)

    for token in tokens:
        token_id = token.token_id
        if not token_id:
            continue
        token_ids.append(token_id)

        for element_id in token.assigned_element_ids or token.source_element_ids:
            if str(element_id).strip():
                element_to_token_ids[str(element_id).strip()].append(token_id)

        for property_ref in token.source_property_refs:
            if str(property_ref).strip():
                style_ref_to_token_ids[str(property_ref).strip()].append(token_id)

        for color_id in token.source_color_ids:
            if str(color_id).strip():
                color_to_token_ids[str(color_id).strip()].append(token_id)

        if token.tone is not None:
            for palette_id in token.source_palette_ids:
                normalized_palette_id = str(palette_id).strip()
                if normalized_palette_id:
                    palette_tone_to_token_ids[
                        f"{normalized_palette_id}:{int(token.tone)}"
                    ].append(token_id)

    return (
        _unique(token_ids),
        {key: _unique(value) for key, value in element_to_token_ids.items()},
        {key: _unique(value) for key, value in style_ref_to_token_ids.items()},
        {key: _unique(value) for key, value in color_to_token_ids.items()},
        {key: _unique(value) for key, value in palette_tone_to_token_ids.items()},
    )


def _extract_style_ids_from_artifact(payload: Any) -> tuple[str, ...]:
    if isinstance(payload, Mapping):
        candidates: list[str] = []
        for value in payload.values():
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                for item in value:
                    if isinstance(item, Mapping):
                        candidates.append(str(item.get("style_id") or ""))
        return _unique(candidates)
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return _unique(
            str(item.get("style_id") or "")
            for item in payload
            if isinstance(item, Mapping)
        )
    return ()


def _extract_color_ids_from_artifact(payload: Any) -> tuple[str, ...]:
    if isinstance(payload, Mapping):
        entries = payload.get("entries")
        if isinstance(entries, Sequence) and not isinstance(entries, (str, bytes, bytearray)):
            return _unique(
                str(item.get("color_id") or "")
                for item in entries
                if isinstance(item, Mapping)
            )
    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return _unique(
            str(item.get("color_id") or "")
            for item in payload
            if isinstance(item, Mapping)
        )
    return ()


def _build_adjacency(
    elements: ElementInventoryModel,
) -> dict[str, tuple[str, ...]]:
    element_lookup = _element_index(elements)
    visible_entries = tuple(entry for entry in elements if entry.flags.is_visible)
    adjacency: dict[str, tuple[str, ...]] = {}

    for entry in elements:
        candidates: dict[str, ElementInventoryEntry] = {}
        if entry.parent_id:
            parent = element_lookup.get(entry.parent_id)
            if parent is not None:
                for sibling_id in parent.children_ids:
                    if sibling_id == entry.node_id:
                        continue
                    sibling = element_lookup.get(sibling_id)
                    if sibling is not None and sibling.flags.is_visible:
                        candidates.setdefault(sibling.node_id, sibling)
        for other in visible_entries:
            if other.node_id == entry.node_id:
                continue
            if _bounds_intersect(entry, other):
                candidates.setdefault(other.node_id, other)
        if candidates:
            adjacency[entry.node_id] = tuple(
                item.node_id
                for item in sorted(
                    candidates.values(),
                    key=lambda item: (item.document_order, item.node_id),
                )
            )
    return adjacency


@dataclass(frozen=True, slots=True)
class InventoryGraphModel:
    element_ids: tuple[str, ...] = field(default_factory=tuple)
    style_ids: tuple[str, ...] = field(default_factory=tuple)
    color_ids: tuple[str, ...] = field(default_factory=tuple)
    token_ids: tuple[str, ...] = field(default_factory=tuple)
    root_ids: tuple[str, ...] = field(default_factory=tuple)
    palettes: tuple[TonalPaletteModel, ...] = field(default_factory=tuple)
    element_to_parent_id: Mapping[str, str] = field(default_factory=dict)
    element_to_children_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    element_to_style_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    element_to_color_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    element_to_token_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    style_ref_to_token_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    color_to_token_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    palette_tone_to_token_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    element_adjacency: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    _elements_ref: ElementInventoryModel = field(
        default_factory=ElementInventoryModel,
        repr=False,
        compare=False,
    )
    _styles_ref: StyleInventoryModel = field(
        default_factory=StyleInventoryModel,
        repr=False,
        compare=False,
    )
    _colors_ref: ColorInventoryModel = field(
        default_factory=ColorInventoryModel,
        repr=False,
        compare=False,
    )
    _tokens_ref: TokenInventoryModel = field(
        default_factory=TokenInventoryModel,
        repr=False,
        compare=False,
    )
    _element_ref_index: Mapping[str, ElementInventoryEntry] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )
    _style_ref_index: Mapping[str, StyleInventoryEntry] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )
    _color_ref_index: Mapping[str, ColorInventoryEntry] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )
    _palette_ref_index: Mapping[str, TonalPaletteModel] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )
    _token_ref_index: Mapping[str, TokenModel] = field(
        default_factory=dict,
        repr=False,
        compare=False,
    )

    @classmethod
    def build(
        cls,
        *,
        elements: ElementInventoryModel,
        styles: StyleInventoryModel,
        colors: ColorInventoryModel,
        palettes: Sequence[TonalPaletteModel] = (),
        tokens: TokenInventoryModel | None = None,
    ) -> Self:
        element_to_style_ids = {
            entry.node_id: _unique(
                [
                    *(style_payload.style_id or "" for _, style_payload in entry.iter_computed_styles()),
                    *(
                        color_property.winning_style_ref.style_id or ""
                        for color_property in entry.iter_color_properties()
                    ),
                ]
            )
            for entry in elements
        }
        element_to_color_ids = {
            entry.node_id: _unique(
                color_property.color_id or "" for color_property in entry.iter_color_properties()
            )
            for entry in elements
        }
        palette_entries = tuple(palettes)
        token_inventory = tokens or TokenInventoryModel()
        (
            token_ids,
            element_to_token_ids,
            style_ref_to_token_ids,
            color_to_token_ids,
            palette_tone_to_token_ids,
        ) = _build_token_relations(token_inventory)

        return cls(
            element_ids=tuple(entry.node_id for entry in elements),
            style_ids=tuple(entry.style_id for entry in styles),
            color_ids=tuple(entry.color_id for entry in colors),
            token_ids=token_ids,
            root_ids=tuple(entry.node_id for entry in elements.roots()),
            palettes=palette_entries,
            element_to_parent_id={
                entry.node_id: entry.parent_id
                for entry in elements
                if entry.parent_id is not None
            },
            element_to_children_ids={
                entry.node_id: _unique(entry.children_ids)
                for entry in elements
                if entry.children_ids
            },
            element_to_style_ids={
                key: tuple(sorted(value))
                for key, value in element_to_style_ids.items()
            },
            element_to_color_ids={
                key: tuple(sorted(value))
                for key, value in element_to_color_ids.items()
            },
            element_to_token_ids=element_to_token_ids,
            style_ref_to_token_ids=style_ref_to_token_ids,
            color_to_token_ids=color_to_token_ids,
            palette_tone_to_token_ids=palette_tone_to_token_ids,
            element_adjacency=_build_adjacency(elements),
            _elements_ref=elements,
            _styles_ref=styles,
            _colors_ref=colors,
            _tokens_ref=token_inventory,
            _element_ref_index=_element_index(elements),
            _style_ref_index=_style_index(styles),
            _color_ref_index=_color_index(colors),
            _palette_ref_index=_palette_index(palette_entries),
            _token_ref_index=_token_index(token_inventory),
        )

    @classmethod
    def build_from_artifact(
        cls,
        payload: Mapping[str, Any],
        *,
        elements: ElementInventoryModel | None = None,
        styles: StyleInventoryModel | None = None,
        colors: ColorInventoryModel | None = None,
        palettes: Sequence[TonalPaletteModel] | None = None,
        tokens: TokenInventoryModel | None = None,
    ) -> Self:
        relations = dict(payload.get("relations") or {})
        graph = cls(
            element_ids=_unique(
                payload.get("element_ids")
                or (
                    item.get("node_id")
                    for item in (payload.get("elements") or ())
                    if isinstance(item, Mapping)
                )
            ),
            style_ids=_unique(
                payload.get("style_ids")
                or _extract_style_ids_from_artifact(payload.get("styles"))
            ),
            color_ids=_unique(
                payload.get("color_ids")
                or _extract_color_ids_from_artifact(payload.get("colors"))
            ),
            token_ids=_unique(payload.get("token_ids") or ()),
            root_ids=_unique(payload.get("root_ids") or ()),
            palettes=tuple(palettes or ()),
            element_to_parent_id={
                str(key).strip(): str(value).strip()
                for key, value in dict(relations.get("element_to_parent_id") or {}).items()
                if str(key).strip() and str(value).strip()
            },
            element_to_children_ids=_normalize_id_map(relations.get("element_to_children_ids")),
            element_to_style_ids=_normalize_id_map(relations.get("element_to_style_ids")),
            element_to_color_ids=_normalize_id_map(relations.get("element_to_color_ids")),
            element_to_token_ids=_normalize_id_map(relations.get("element_to_token_ids")),
            style_ref_to_token_ids=_normalize_id_map(relations.get("style_ref_to_token_ids")),
            color_to_token_ids=_normalize_id_map(relations.get("color_to_token_ids")),
            palette_tone_to_token_ids=_normalize_id_map(relations.get("palette_tone_to_token_ids")),
            element_adjacency=_normalize_id_map(relations.get("element_adjacency")),
        )
        if elements is None and styles is None and colors is None and palettes is None and tokens is None:
            return graph
        return graph.bind_inventories(
            elements=elements or ElementInventoryModel(),
            styles=styles or StyleInventoryModel(),
            colors=colors or ColorInventoryModel(),
            palettes=palettes,
            tokens=tokens,
        )

    @property
    def elements(self) -> ElementInventoryModel:
        return self._elements_ref

    @property
    def styles(self) -> StyleInventoryModel:
        return self._styles_ref

    @property
    def colors(self) -> ColorInventoryModel:
        return self._colors_ref

    @property
    def tokens(self) -> TokenInventoryModel:
        return self._tokens_ref

    def bind_inventories(
        self,
        *,
        elements: ElementInventoryModel,
        styles: StyleInventoryModel,
        colors: ColorInventoryModel,
        palettes: Sequence[TonalPaletteModel] | None = None,
        tokens: TokenInventoryModel | None = None,
    ) -> Self:
        palette_entries = tuple(self.palettes if palettes is None else palettes)
        token_inventory = self.tokens if tokens is None else tokens
        (
            token_ids,
            element_to_token_ids,
            style_ref_to_token_ids,
            color_to_token_ids,
            palette_tone_to_token_ids,
        ) = _build_token_relations(token_inventory)
        return replace(
            self,
            token_ids=token_ids,
            palettes=palette_entries,
            element_to_token_ids=element_to_token_ids,
            style_ref_to_token_ids=style_ref_to_token_ids,
            color_to_token_ids=color_to_token_ids,
            palette_tone_to_token_ids=palette_tone_to_token_ids,
            _elements_ref=elements,
            _styles_ref=styles,
            _colors_ref=colors,
            _tokens_ref=token_inventory,
            _element_ref_index=_element_index(elements),
            _style_ref_index=_style_index(styles),
            _color_ref_index=_color_index(colors),
            _palette_ref_index=_palette_index(palette_entries),
            _token_ref_index=_token_index(token_inventory),
        )

    def element_by_id(self, node_id: str) -> ElementInventoryEntry | None:
        return self._element_ref_index.get(node_id)

    def style_by_id(self, style_id: str) -> StyleInventoryEntry | None:
        return self._style_ref_index.get(style_id)

    def color_by_id(self, color_id: str) -> ColorInventoryEntry | None:
        return self._color_ref_index.get(color_id)

    def palette_by_id(self, palette_id: str) -> TonalPaletteModel | None:
        return self._palette_ref_index.get(palette_id)

    def token_by_id(self, token_id: str) -> TokenModel | None:
        return self._token_ref_index.get(token_id)

    def tokens_for_element(self, node_id: str) -> tuple[TokenModel, ...]:
        token_ids = self.element_to_token_ids.get(node_id, ())
        return tuple(
            token for token in (self.token_by_id(token_id) for token_id in token_ids) if token is not None
        )

    def tokens_for_style_ref(self, style_ref: str) -> tuple[TokenModel, ...]:
        token_ids = self.style_ref_to_token_ids.get(style_ref, ())
        return tuple(
            token for token in (self.token_by_id(token_id) for token_id in token_ids) if token is not None
        )

    def tokens_for_color(self, color_id: str) -> tuple[TokenModel, ...]:
        token_ids = self.color_to_token_ids.get(color_id, ())
        return tuple(
            token for token in (self.token_by_id(token_id) for token_id in token_ids) if token is not None
        )

    def tokens_for_palette_tone(self, palette_id: str, tone: int) -> tuple[TokenModel, ...]:
        token_ids = self.palette_tone_to_token_ids.get(f"{palette_id}:{int(tone)}", ())
        return tuple(
            token for token in (self.token_by_id(token_id) for token_id in token_ids) if token is not None
        )

    def parent_of(self, node_id: str) -> ElementInventoryEntry | None:
        parent_id = self.element_to_parent_id.get(node_id)
        if parent_id is None:
            entry = self.element_by_id(node_id)
            if entry is None or entry.parent_id is None:
                return None
            parent_id = entry.parent_id
        return self.element_by_id(parent_id)

    def children_of(self, node_id: str) -> tuple[ElementInventoryEntry, ...]:
        child_ids = self.element_to_children_ids.get(node_id)
        if child_ids is None:
            return self.elements.children_of(node_id)
        children = [self.element_by_id(child_id) for child_id in child_ids]
        return tuple(child for child in children if child is not None)

    def ancestors_of(self, node_id: str) -> tuple[ElementInventoryEntry, ...]:
        ancestors: list[ElementInventoryEntry] = []
        current = self.parent_of(node_id)
        while current is not None:
            ancestors.append(current)
            current = self.parent_of(current.node_id)
        return tuple(ancestors)

    def descendants_of(self, node_id: str) -> tuple[ElementInventoryEntry, ...]:
        descendants: list[ElementInventoryEntry] = []
        for child in self.children_of(node_id):
            descendants.append(child)
            descendants.extend(self.descendants_of(child.node_id))
        return tuple(descendants)

    def siblings_of(self, node_id: str) -> tuple[ElementInventoryEntry, ...]:
        parent_id = self.element_to_parent_id.get(node_id)
        if parent_id is None:
            entry = self.element_by_id(node_id)
            if entry is None or entry.parent_id is None:
                return ()
            parent_id = entry.parent_id
        siblings = [item for item in self.children_of(parent_id) if item.node_id != node_id]
        return tuple(siblings)

    def previous_visible_sibling(self, node_id: str) -> ElementInventoryEntry | None:
        siblings = sorted(
            [item for item in self.siblings_of(node_id) if item.flags.is_visible],
            key=lambda item: item.document_order,
        )
        current = self.element_by_id(node_id)
        if current is None:
            return None
        previous = [item for item in siblings if item.document_order < current.document_order]
        return previous[-1] if previous else None

    def next_visible_sibling(self, node_id: str) -> ElementInventoryEntry | None:
        siblings = sorted(
            [item for item in self.siblings_of(node_id) if item.flags.is_visible],
            key=lambda item: item.document_order,
        )
        current = self.element_by_id(node_id)
        if current is None:
            return None
        next_items = [item for item in siblings if item.document_order > current.document_order]
        return next_items[0] if next_items else None

    def effective_background_of(self, node_id: str) -> ColorInventoryEntry | None:
        entry = self.element_by_id(node_id)
        if entry is None:
            return None
        if entry.styles.effective_background_color_id:
            background = self.color_by_id(entry.styles.effective_background_color_id)
            if background is not None:
                return background
        for candidate in (entry, *self.ancestors_of(node_id)):
            for color_property in candidate.color_properties:
                if color_property.property_name == "background-color" and color_property.color_id:
                    color_entry = self.color_by_id(color_property.color_id)
                    if color_entry is not None:
                        return color_entry
        return None

    def effective_color_of(self, node_id: str) -> ColorInventoryEntry | None:
        entry = self.element_by_id(node_id)
        if entry is None:
            return None
        for candidate in (entry, *self.ancestors_of(node_id)):
            for color_property in candidate.color_properties:
                if color_property.property_name == "color" and color_property.color_id:
                    color_entry = self.color_by_id(color_property.color_id)
                    if color_entry is not None:
                        return color_entry
        return None

    def surface_container_of(self, node_id: str) -> ElementInventoryEntry | None:
        entry = self.element_by_id(node_id)
        if entry is None:
            return None
        for candidate in (entry, *self.ancestors_of(node_id)):
            has_background = any(
                color_property.property_name == "background-color" and color_property.color_id
                for color_property in candidate.color_properties
            )
            if has_background or candidate.styles.effective_background_color_id is not None:
                return candidate
        return None

    def adjacent_elements_of(self, node_id: str) -> tuple[ElementInventoryEntry, ...]:
        adjacent_ids = self.element_adjacency.get(node_id)
        if adjacent_ids is None:
            entry = self.element_by_id(node_id)
            if entry is None:
                return ()
            candidates = {
                sibling.node_id: sibling
                for sibling in self.siblings_of(node_id)
                if sibling.flags.is_visible
            }
            for other in self.elements.visible_entries():
                if other.node_id == node_id:
                    continue
                if _bounds_intersect(entry, other):
                    candidates.setdefault(other.node_id, other)
            return tuple(
                sorted(candidates.values(), key=lambda item: (item.document_order, item.node_id))
            )
        adjacent = [self.element_by_id(item) for item in adjacent_ids]
        return tuple(item for item in adjacent if item is not None)

    def to_artifact_dict(self) -> dict[str, Any]:
        relations: dict[str, Any] = {}
        if self.element_to_parent_id:
            relations["element_to_parent_id"] = dict(self.element_to_parent_id)
        if self.element_to_children_ids:
            relations["element_to_children_ids"] = {
                key: list(value) for key, value in self.element_to_children_ids.items()
            }
        if self.element_to_style_ids:
            relations["element_to_style_ids"] = {
                key: list(value) for key, value in self.element_to_style_ids.items()
            }
        if self.element_to_color_ids:
            relations["element_to_color_ids"] = {
                key: list(value) for key, value in self.element_to_color_ids.items()
            }
        if self.element_to_token_ids:
            relations["element_to_token_ids"] = {
                key: list(value) for key, value in self.element_to_token_ids.items()
            }
        if self.style_ref_to_token_ids:
            relations["style_ref_to_token_ids"] = {
                key: list(value) for key, value in self.style_ref_to_token_ids.items()
            }
        if self.color_to_token_ids:
            relations["color_to_token_ids"] = {
                key: list(value) for key, value in self.color_to_token_ids.items()
            }
        if self.palette_tone_to_token_ids:
            relations["palette_tone_to_token_ids"] = {
                key: list(value) for key, value in self.palette_tone_to_token_ids.items()
            }
        if self.element_adjacency:
            relations["element_adjacency"] = {
                key: list(value) for key, value in self.element_adjacency.items()
            }
        return {
            "root_ids": list(self.root_ids),
            "element_ids": list(self.element_ids),
            "style_ids": list(self.style_ids),
            "color_ids": list(self.color_ids),
            "token_ids": list(self.token_ids),
            "relations": relations,
        }

    def to_dict(self) -> dict[str, Any]:
        return self.to_artifact_dict()
