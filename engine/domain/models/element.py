from __future__ import annotations

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from engine.domain.models.color import Color, unique_colors

_HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b")
_FUNCTION_COLOR_RE = re.compile(r"rgba?\([^)]+\)", re.IGNORECASE)


@dataclass(slots=True)
class Property:
    name: str
    value: str
    colors: tuple[Color, ...] = field(default_factory=tuple)
    style_id: str | None = None

    def __post_init__(self) -> None:
        self.name = str(self.name or "").strip()
        self.value = str(self.value or "").strip()
        if not self.colors:
            self.colors = extract_colors(self.value)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
        }
        if self.colors:
            payload["colors"] = [color.to_dict() for color in self.colors]
        if self.style_id is not None:
            payload["style_id"] = self.style_id
        return payload


@dataclass(slots=True)
class Element:
    backend_node_id: int
    node_id: int
    tag_name: str
    node_type: int
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    is_text_node: bool = False
    role: str | None = None
    font_size: str | None = None
    font_weight: str | None = None
    properties: list[Property] = field(default_factory=list)
    children: list["Element"] = field(default_factory=list, repr=False)
    parent: "Element | None" = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.backend_node_id = int(self.backend_node_id)
        self.node_id = int(self.node_id)
        self.node_type = int(self.node_type)
        self.tag_name = str(self.tag_name or "").strip().lower()

    def add_child(self, child: "Element") -> None:
        if not isinstance(child, Element):
            raise TypeError("child must be an Element instance.")
        if child is self:
            raise ValueError("An Element cannot be a child of itself.")
        if child not in self.children:
            child.parent = self
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

    def filter(self, condition: Callable[["Element"], bool]) -> tuple["Element", ...]:
        return tuple(element for element in self.iter_dfs() if condition(element))

    @property
    def all_colors(self) -> tuple[Color, ...]:
        return unique_colors(color for prop in self.properties for color in prop.colors)

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend_node_id": self.backend_node_id,
            "node_id": self.node_id,
            "tag_name": self.tag_name,
            "node_type": self.node_type,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "is_text_node": self.is_text_node,
            "role": self.role,
            "font_size": self.font_size,
            "font_weight": self.font_weight,
            "properties": [prop.to_dict() for prop in self.properties],
            "children": [child.to_dict() for child in self.children],
        }


def extract_colors(value: str) -> tuple[Color, ...]:
    colors: list[Color] = []
    for token in (*_HEX_COLOR_RE.findall(value), *_FUNCTION_COLOR_RE.findall(value)):
        color = Color.from_css(token)
        if color is not None and color not in colors:
            colors.append(color)
    return tuple(colors)


def iter_elements(root: Element | None) -> Iterable[Element]:
    return () if root is None else root.iter_dfs()
