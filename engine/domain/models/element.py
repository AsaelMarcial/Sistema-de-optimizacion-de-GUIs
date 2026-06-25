from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable

@dataclass(slots=True)
class Attribute:
    name: str
    value: str

@dataclass(slots=True)
class Property:
    name: str
    value: str
    has_color: bool = False
    style_id: str | None = None

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
    role: str | None = None
    attributes: list[Attribute] = field(default_factory=list)
    properties: list[Property] = field(default_factory=list)
    children: list["Element"] = field(default_factory=list, repr=False)

    @property
    def is_text_node(self) -> bool:
        return self.tag_name == "#text" and not self.children

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


def iter_elements(root: Element | None) -> Iterable[Element]:
    return () if root is None else root.iter_dfs()
