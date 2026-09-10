from __future__ import annotations

import builtins
from collections import deque
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from engine.domain.data.scope_css import get_font_weight
from engine.domain.data.scope_html_elements import get_html_elements_by_category
from engine.domain.models.color_scheme import Color
from engine.domain.models.project_context import Resource
from engine.domain.utils.parsers import are_all_colors_transparent, get_colors

BoxQuad = list[tuple[float, float]]

PropertyType = Literal[
    "inline",
    "inherited",
    "matched",
    "attribute",
]


@dataclass(slots=True)
class Property:
    name: str
    before_value: str | None = field(default="")
    value_tokens: tuple[Any, ...] = field(
        default_factory=tuple,
        repr=False,
        hash=False,
        compare=False,
    )
    after_value: str | None = field(default=None)
    calculated_value: str | None = field(default=None)
    resource: Resource | None = field(
        default=None, repr=False, hash=False, compare=False
    )
    has_color: bool = False
    type: PropertyType = field(default="matched")
    is_defined: bool = field(default=False)

    @property
    def resource_loaded(self) -> bool:
        return self.resource is not None and self.resource.is_loaded

    @property
    def current_value(self) -> str:
        return (self.after_value if self.has_changed else self.before_value) or ""

    @property
    def has_changed(self) -> bool:
        return self.after_value is not None and self.before_value != self.after_value


@dataclass(slots=True, eq=False)
class Element:
    backend_node_id: int
    node_id: int | None
    tag_name: str
    category: str | None
    node_type: int
    node_value: str | None = None
    parent: Element | None = field(
        default=None, init=False, repr=False, hash=False, compare=False
    )
    box_model: dict[str, BoxQuad] | None = field(default=None)
    width: float | None = field(default=None)
    height: float | None = field(default=None)
    attributes: list[Property] = field(
        default_factory=list, repr=False, hash=False, compare=False
    )
    properties: list[Property] = field(default_factory=list)
    image_references: list[Property] = field(
        default_factory=list, repr=False, hash=False, compare=False
    )
    children: list[Element] = field(
        default_factory=list, repr=False, hash=False, compare=False
    )

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Element) and self.backend_node_id == other.backend_node_id
        )

    def __hash__(self) -> int:
        return hash(self.backend_node_id)

    @property
    def ancestors(self) -> Iterator[Element]:
        current = self.parent
        visited_backend_node_ids: set[int] = {self.backend_node_id}

        while current is not None:
            if current.backend_node_id in visited_backend_node_ids:
                break

            yield current
            visited_backend_node_ids.add(current.backend_node_id)
            current = current.parent

    @property
    def is_visible(self) -> bool:
        return bool(self.box_model and (self.width or 0) > 0 and (self.height or 0) > 0)

    @property
    def depth(self) -> int:
        return self.depth_for()

    def depth_for(self, only_visible_ancestors: bool = True) -> int:
        depth = 1
        for ancestor in self.ancestors:
            if ancestor.tag_name == "body":
                break
            if not only_visible_ancestors or ancestor.is_visible:
                depth += 1
        return depth

    @property
    def has_text(self) -> bool:
        return any(
            child.tag_name == "#text" and bool(str(child.node_value or "").strip())
            for child in self.children
        )

    @property
    def has_image(self) -> bool:
        return bool(self.image_references)

    @property
    def content(self) -> BoxQuad | None:
        return None if self.box_model is None else self.box_model.get("content")

    @property
    def padding(self) -> BoxQuad | None:
        return None if self.box_model is None else self.box_model.get("padding")

    @property
    def border(self) -> BoxQuad | None:
        return None if self.box_model is None else self.box_model.get("border")

    @property
    def margin(self) -> BoxQuad | None:
        return None if self.box_model is None else self.box_model.get("margin")

    def add_child(self, child: Element) -> None:
        if child is self:
            raise ValueError("An Element cannot be a child of itself.")
        if not any(
            item.backend_node_id == child.backend_node_id for item in self.children
        ):
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

    def attribute(self, name: str) -> Property | None:
        normalized = str(name).strip()
        return next((attr for attr in self.attributes if attr.name == normalized), None)

    def property(self, name: str) -> dict[str, Any]:
        """
        Busca una propiedad por su nombre y devuelve un diccionario con
        todos sus atributos. Si no existe, devuelve valores seguros por defecto.
        """
        normalized = str(name).strip().lower() if name is not None else ""
        prop = next(
            (
                p
                for p in self.properties
                if p.name == normalized and p.type != "attribute"
            ),
            None,
        )

        return {
            "name": prop.name if prop is not None else "",
            "before_value": prop.before_value
            if prop is not None and prop.before_value is not None
            else "",
            "after_value": prop.after_value if prop is not None else None,
            "calculated_value": prop.calculated_value if prop is not None else None,
            "resource": prop.resource if prop is not None else None,
            "has_color": prop.has_color if prop is not None else False,
            "is_defined": prop.is_defined if prop is not None else False,
            "type": prop.type if prop is not None else "inherited",
            "current_value": prop.current_value if prop is not None else "",
            "has_changed": prop.has_changed if prop is not None else False,
        }

    def remove_property(self, name: str) -> None:
        normalized = str(name).strip()
        self.properties[:] = [
            prop
            for prop in self.properties
            if prop.name != normalized or prop.type == "attribute"
        ]

    def get_text_contrast(
        self,
        color: str,
        background_colors: Iterable[str],
        font_size: Any,
        font_weight: Any,
    ) -> tuple[str, Color, float, float, bool] | None:
        background_values = tuple(background_colors or ())
        if not color or not background_values:
            # print(str(color))
            return None

        foreground = Color(color)

        background, contrast_ratio = min(
            (
                (background := Color(value), foreground.contrast(background))
                for value in background_values
            ),
            key=lambda item: item[1],
        )

        try:
            font_size = float(str(font_size).removesuffix("px"))
        except (TypeError, ValueError):
            # print(str(font_size))
            return None

        font_weight = get_font_weight(str(font_weight)) or 400
        is_large_text = font_size >= 24 or font_size >= 56 / 3 and font_weight >= 700
        required_ratio = 3.0 if is_large_text else 4.5

        return (
            foreground.convert("srgb").to_string(
                comma=True, alpha=True, rounding="decimal", precision=0
            ),
            background,
            float(contrast_ratio),
            required_ratio,
            is_large_text,
        )

    @builtins.property
    def effective_background(self) -> dict[str, Any]:
        """
        Determina y devuelve el diccionario de la propiedad de fondo
        efectiva del elemento, resolviendo transparencias y contenidos.
        """
        for property_name in (
            "fill",
            "background",
            "background-image",
            "background-color",
        ):
            # Almacenamos el diccionario de la propiedad una sola vez para mejorar rendimiento
            prop = self.property(property_name)
            prop_value = prop[
                "current_value"
            ]  # Coincide exactamente con tu nueva clave

            match prop["name"]:
                case "background":
                    bg_image_name = self.property("background-image")["name"]

                    if self.has_image and bg_image_name != "":
                        continue
                    return prop

                case "fill":
                    if (
                        self.tag_name in get_html_elements_by_category("decoration")
                        and get_colors(prop_value) is not None
                        and not are_all_colors_transparent(prop_value)
                    ):
                        return prop

                case "background-image":
                    # Usamos las banderas booleanas seguras de tu propio diccionario
                    if (not self.has_image and not prop["has_color"]) or (
                        prop["has_color"] and are_all_colors_transparent(prop_value)
                    ):
                        continue
                    return prop

                case "background-color":
                    if not are_all_colors_transparent(prop_value):
                        return prop

        # Si ninguna propiedad de fondo es efectiva, devuelve el diccionario seguro por defecto
        return self.property("")

    def get_effective_parent_background(self, root: Element) -> Element:
        """
        Devuelve el ancestro más cercano que tenga al menos un color de
        fondo válido. Si ninguno tiene, devuelve el nodo 'root'.
        """
        for ancestor in self.ancestors:
            if ancestor.tag_name == "body" or ancestor.has_image:
                return ancestor

            bg_prop = ancestor.effective_background
            bg_value = bg_prop["current_value"]

            if (
                bg_prop["name"]
                and ancestor.tag_name not in get_html_elements_by_category("decoration")
                and get_colors(bg_value) is not None
                and not are_all_colors_transparent(bg_value)
            ):
                return ancestor

        # Retorno de cortocircuito seguro si ningún ancestro aportó color
        return root


@dataclass(slots=True)
class DomTree:
    html: Element | None = None
    body: Element | None = None
    elements: dict[int, Element] = field(default_factory=dict)
    stylesheet_owners: dict[int, Element] = field(default_factory=dict)
    meta_elements: dict[int, Element] = field(default_factory=dict)
    page_width: int = 0
    page_height: int = 0

    @property
    def root(self) -> Element | None:
        return self.html

    @property
    def size(self) -> tuple[int, int]:
        return self.page_width, self.page_height

    def require_html(self) -> Element:
        if self.html is None:
            raise RuntimeError("DomTree no contiene html.")
        return self.html

    def require_body(self) -> Element:
        if self.body is None:
            raise RuntimeError("DomTree no contiene body.")
        return self.body

    def iter_dfs(self) -> Iterable[Element]:
        body = self.body
        return () if body is None else body.iter_dfs()

    def iter_full_dfs(self) -> Iterable[Element]:
        html = self.html
        return () if html is None else html.iter_dfs()

    def get(self, backend_node_id: int) -> Element | None:
        return self.elements.get(backend_node_id)

    def find(self, condition: Callable[[Element], bool]) -> Element | None:
        return next(
            (element for element in self.elements.values() if condition(element)),
            None,
        )

    def find_by_backend_node_id(
        self,
        backend_node_id: int,
    ) -> Element | None:
        return self.elements.get(backend_node_id)

    def filter(
        self,
        condition: Callable[[Element], bool],
    ) -> dict[int, Element]:
        return {
            backend_node_id: element
            for backend_node_id, element in self.elements.items()
            if condition(element)
        }
