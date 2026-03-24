from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence, Self

from engine.domain.models.color import ColorInventoryEntry, ColorInventoryModel
from engine.domain.models.element import ElementInventoryEntry, ElementInventoryModel
from engine.domain.models.palette import TonalPaletteModel
from engine.domain.models.style import StyleInventoryEntry, StyleInventoryModel
from engine.domain.models.token import TokenInventoryModel, TokenModel


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)).keys())


def _style_ref_key(style_id: str, property_name: str) -> str:
    return f"{style_id}:{property_name}"


def _palette_tone_key(palette_id: str, tone: int) -> str:
    return f"{palette_id}:{tone}"


def _bounds_intersect(left: ElementInventoryEntry, right: ElementInventoryEntry) -> bool:
    a = left.layout.absolute_bounds
    b = right.layout.absolute_bounds
    return not (
        a.right <= b.left
        or a.left >= b.right
        or a.bottom <= b.top
        or a.top >= b.bottom
    )


@dataclass(frozen=True, slots=True)
class InventoryGraphModel:
    elements: ElementInventoryModel
    styles: StyleInventoryModel
    colors: ColorInventoryModel
    palettes: tuple[TonalPaletteModel, ...] = field(default_factory=tuple)
    tokens: TokenInventoryModel = field(default_factory=TokenInventoryModel)
    element_to_style_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    element_to_color_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    element_to_token_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    color_to_token_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    palette_tone_to_token_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    style_declaration_to_token_ids: Mapping[str, tuple[str, ...]] = field(default_factory=dict)

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
        token_inventory = tokens or TokenInventoryModel()

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

        element_token_map: dict[str, list[str]] = {}
        color_token_map: dict[str, list[str]] = {}
        palette_token_map: dict[str, list[str]] = {}
        style_token_map: dict[str, list[str]] = {}
        for token in token_inventory:
            for element_id in token.assigned_element_ids:
                element_token_map.setdefault(element_id, []).append(token.token_id)
            for color_id in token.source_color_ids:
                color_token_map.setdefault(color_id, []).append(token.token_id)
            for palette_id in token.source_palette_ids:
                if token.tone is not None:
                    palette_token_map.setdefault(
                        _palette_tone_key(palette_id, token.tone),
                        [],
                    ).append(token.token_id)
            for style_id in token.source_style_ids:
                for property_name in token.source_property_names:
                    style_token_map.setdefault(
                        _style_ref_key(style_id, property_name),
                        [],
                    ).append(token.token_id)

        return cls(
            elements=elements,
            styles=styles,
            colors=colors,
            palettes=tuple(palettes),
            tokens=token_inventory,
            element_to_style_ids={key: tuple(sorted(value)) for key, value in element_to_style_ids.items()},
            element_to_color_ids={key: tuple(sorted(value)) for key, value in element_to_color_ids.items()},
            element_to_token_ids={key: tuple(sorted(value)) for key, value in element_token_map.items()},
            color_to_token_ids={key: tuple(sorted(value)) for key, value in color_token_map.items()},
            palette_tone_to_token_ids={
                key: tuple(sorted(value)) for key, value in palette_token_map.items()
            },
            style_declaration_to_token_ids={
                key: tuple(sorted(value)) for key, value in style_token_map.items()
            },
        )

    @property
    def root_ids(self) -> tuple[str, ...]:
        return tuple(entry.node_id for entry in self.elements.roots())

    def element_by_id(self, node_id: str) -> ElementInventoryEntry | None:
        return self.elements.entry_by_id(node_id)

    def style_by_id(self, style_id: str) -> StyleInventoryEntry | None:
        return self.styles.entry_by_id(style_id)

    def color_by_id(self, color_id: str) -> ColorInventoryEntry | None:
        return self.colors.entry_by_id(color_id)

    def palette_by_id(self, palette_id: str) -> TonalPaletteModel | None:
        return next((palette for palette in self.palettes if palette.palette_id == palette_id), None)

    def token_by_id(self, token_id: str) -> TokenModel | None:
        return self.tokens.entry_by_id(token_id)

    def parent_of(self, node_id: str) -> ElementInventoryEntry | None:
        entry = self.element_by_id(node_id)
        if entry is None or entry.parent_id is None:
            return None
        return self.element_by_id(entry.parent_id)

    def children_of(self, node_id: str) -> tuple[ElementInventoryEntry, ...]:
        return self.elements.children_of(node_id)

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
        entry = self.element_by_id(node_id)
        if entry is None or entry.parent_id is None:
            return ()
        siblings = [item for item in self.children_of(entry.parent_id) if item.node_id != node_id]
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
        return tuple(sorted(candidates.values(), key=lambda item: (item.document_order, item.node_id)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_ids": list(self.root_ids),
            "elements": [entry.to_dict() for entry in self.elements],
            "styles": self.styles.to_dict(),
            "colors": self.colors.to_dict(),
            "palettes": [palette.to_dict() for palette in self.palettes],
            "tokens": self.tokens.to_rows(),
            "relations": {
                "element_to_style_ids": {
                    key: list(value) for key, value in self.element_to_style_ids.items()
                },
                "element_to_color_ids": {
                    key: list(value) for key, value in self.element_to_color_ids.items()
                },
                "element_to_token_ids": {
                    key: list(value) for key, value in self.element_to_token_ids.items()
                },
                "color_to_token_ids": {
                    key: list(value) for key, value in self.color_to_token_ids.items()
                },
                "palette_tone_to_token_ids": {
                    key: list(value) for key, value in self.palette_tone_to_token_ids.items()
                },
                "style_declaration_to_token_ids": {
                    key: list(value)
                    for key, value in self.style_declaration_to_token_ids.items()
                },
            },
        }
