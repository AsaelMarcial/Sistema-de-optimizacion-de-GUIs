from __future__ import annotations

import builtins
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable

from engine.domain.utils.parsers import get_colors, is_url_image
from engine.domain.data.scope_css import get_font_weight

from engine.domain.models.color_scheme import Color


@dataclass(slots=True)
class Attribute:
    name: str
    value: str


@dataclass(slots=True)
class Property:
    name: str
    before_value: str| None = field(default="")
    after_value: str | None = field(default=None)
    token_value: str | None = field(default=None)
    has_color: bool = False

    @property
    def has_changed(self) -> bool:
        return self.after_value is not None and self.before_value != self.after_value

@dataclass(slots=True)
class Element:
    backend_node_id: int
    node_id: int | None
    tag_name: str
    category: str | None
    node_type: int
    parent_backend_node_id: int = -1
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    depth: int | None = None
    attributes: list[Attribute] = field(default_factory=list)
    properties: list[Property] = field(default_factory=list)
    children: list["Element"] = field(default_factory=list, repr=False)

    @property
    def has_text(self) -> bool:
        return any(child.tag_name == "#text" for child in self.children)
    
    @property
    def has_image(self) -> bool:
        return any(
            is_url_image(property.before_value)
            for property in self.properties
        ) or any(
            is_url_image(attribute.value)
            for attribute in self.attributes
        )

    def add_child(self, child: "Element") -> None:
        if child is self:
            raise ValueError("An Element cannot be a child of itself.")
        if child not in self.children:
            child.parent_backend_node_id = self.backend_node_id
            self.children.append(child)

    def iter_dfs(self):
        yield self
        for child in self.children:
            yield from child.iter_dfs()

    def iter_bfs(self):
        queue: deque[Element] = deque([self])
        while queue:
            current = queue.popleft()
            yield current
            queue.extend(current.children)

    def find(self, condition: Callable[["Element"], bool]) -> "Element | None":
        for element in self.iter_dfs():
            if condition(element):
                return element
        return None

    def find_by_backend_node_id(self, backend_node_id: int) -> "Element | None":
        return self.find(lambda element: element.backend_node_id == backend_node_id)

    def ancestors_of(self, node: Element) -> list[Element]:
        elements_by_backend_node_id = {
            element.backend_node_id: element
            for element in self.iter_dfs()
        }
        ancestors: list[Element] = []
        parent_backend_node_id = node.parent_backend_node_id
        visited_backend_node_ids: set[int] = {node.backend_node_id}

        while parent_backend_node_id != -1:
            if parent_backend_node_id in visited_backend_node_ids:
                break

            parent = elements_by_backend_node_id.get(parent_backend_node_id)
            if parent is None:
                break

            ancestors.append(parent)
            visited_backend_node_ids.add(parent.backend_node_id)
            parent_backend_node_id = parent.parent_backend_node_id

        return ancestors

    def attribute(self, name: str) -> Attribute | None:
        normalized = str(name).strip()
        return next((attr for attr in self.attributes if attr.name == normalized), None)

    def property(self, name: str) -> Property | None:
        normalized = str(name).strip()
        return next((prop for prop in self.properties if prop.name == normalized), None)

    def remove_property(self, name: str) -> None:
        normalized = str(name).strip()
        self.properties[:] = [
            prop for prop in self.properties if prop.name != normalized
        ]

    def has_tag(self, *names: str) -> bool:
        normalized = {str(name).strip().lower() for name in names}
        return self.tag_name.lower() in normalized

    def get_text_contrast(
        self,
        background_colors: Iterable[str],
        font_size: object,
        font_weight: object,
    ) -> tuple[Color, Color, float, float, bool] | None:
        color_property = self.property("color")
        if color_property is None:
            return None

        color_value = (
            color_property.after_value
            if color_property.has_changed
            else color_property.before_value
        )
        text_color = get_colors(color_value)[0][1]
        if not text_color or background_colors is None:
            return None

        background, contrast_ratio = min(
            (
                (background := Color(value), text_color.contrast(background))
                for value in background_colors
            ),
            key=lambda item: item[1],
        )
        
        font_size = float(str(font_size).removesuffix("px"))
        font_weight = get_font_weight(str(font_weight))
        is_large_text = (
            font_size >= 24
            or font_size >= 56 / 3 and font_weight >= 700
        )
        required_ratio = 3.0 if is_large_text else 4.5

        return (
            text_color,
            background,
            float(contrast_ratio),
            required_ratio,
            is_large_text,
        )


    @builtins.property
    def effective_background(self) -> Property | None:
        """
        La propiedad de fondo
        del elemento.
        """
        for property_name in ("background-color", "background-image", "fill"):
            css_property = self.property(property_name)

            if css_property is not None:
                return css_property

        return None

    def get_effective_parent_background(
        self,
        root: "Element",
    ) -> "Element | None":
        """
        Devuelve el ancestro más cercano que tenga al menos un color de
        fondo válido.

        Los ancestros se recorren desde el parent directo hasta el más
        lejano. Devuelve None si ninguno tiene un color de fondo.
        """

        for ancestor in root.ancestors_of(self):
            if ancestor.tag_name == "body":
                return ancestor
            if ancestor.effective_background is not None:
                return ancestor

        return None

def iter_elements(root: Element | None) -> Iterable[Element]:
    return () if root is None else root.iter_dfs()
