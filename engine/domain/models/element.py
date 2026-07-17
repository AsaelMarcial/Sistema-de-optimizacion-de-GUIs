from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable

from engine.domain.models.color_scheme import Color


@dataclass(slots=True)
class Attribute:
    name: str
    value: str


@dataclass(slots=True)
class Property:
    name: str
    before_value: str
    after_value: str | None = field(default=None)
    has_color: bool = False

    @property
    def has_changed(self) -> bool:
        return self.after_value is not None and self.before_value != self.after_value

    def get_colors(self) -> list[tuple[str, Color]]:
        colors = []
        start = 0

        while start < len(self.before_value):
            match = Color.match(self.before_value, start=start, fullmatch=False)

            if match is None:
                start += 1
                continue

            if match.color.alpha(nans=False) > 0:
                colors.append(
                    (
                        self.before_value[match.start:match.end],
                        match.color,
                    )
                )

            start = max(match.end, start + 1)

        return colors


@dataclass(slots=True)
class Element:
    backend_node_id: int
    node_id: int | None
    tag_name: str
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

    def ancestors_of(self, node: "Element | int") -> tuple["Element", ...]:
        target = (
            node
            if isinstance(node, Element)
            else self.find_by_backend_node_id(int(node))
        )
        if target is None:
            return ()

        elements_by_backend_node_id = {
            element.backend_node_id: element
            for element in self.iter_dfs()
        }
        ancestors: list[Element] = []
        parent_backend_node_id = target.parent_backend_node_id
        visited_backend_node_ids: set[int] = {target.backend_node_id}

        while parent_backend_node_id != -1:
            if parent_backend_node_id in visited_backend_node_ids:
                break

            parent = elements_by_backend_node_id.get(parent_backend_node_id)
            if parent is None:
                break

            ancestors.append(parent)
            visited_backend_node_ids.add(parent.backend_node_id)
            parent_backend_node_id = parent.parent_backend_node_id

        return tuple(ancestors)

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

        foreground_colors = color_property.get_colors()
        if not foreground_colors or not background_colors:
            return None

        foreground = foreground_colors[0][1]
        background, contrast_ratio = min(
            (
                (background := Color(value), foreground.contrast(background))
                for value in background_colors
            ),
            key=lambda item: item[1],
        )
        font_size = float(str(font_size).removesuffix("px"))
        font_weight = int(font_weight)
        is_large_text = (
            font_size >= 24
            or font_size >= 56 / 3 and font_weight >= 700
        )
        required_ratio = 3.0 if is_large_text else 4.5

        return (
            foreground,
            background,
            float(contrast_ratio),
            required_ratio,
            is_large_text,
        )


def iter_elements(root: Element | None) -> Iterable[Element]:
    return () if root is None else root.iter_dfs()
