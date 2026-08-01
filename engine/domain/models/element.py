from __future__ import annotations

import builtins
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from engine.domain.data.scope_css import get_font_weight
from engine.domain.utils.parsers import get_colors, has_url_image, are_all_colors_transparent

from engine.domain.models.color_scheme import Color

SVG_PAINT_TAGS = ("svg", "circle", "rect", "ellipse", "line", "polyline", "polygon", "path")

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
    in_css: bool = field(default=False)

    @property
    def current_value(self) -> str:
        return (self.after_value if self.has_changed else self.before_value) or ""

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
    children: list[Element] = field(default_factory=list, repr=False)

    @property
    def has_text(self) -> bool:
        return any(child.tag_name == "#text" for child in self.children)
    
    @property
    def has_image(self) -> bool:
        return bool(self.image_references())

    def image_references(self) -> list[str]:
        references: list[str] = []

        for attribute in self.attributes:
            if has_url_image(attribute.value):
                references.append(attribute.value)

        for property in self.properties:
            if has_url_image(property.before_value):
                references.append(property.before_value)

        return references

    def add_child(self, child: Element) -> None:
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

    def find(self, condition: Callable[[Element], bool]) -> Element | None:
        for element in self.iter_dfs():
            if condition(element):
                return element
        return None

    def find_by_backend_node_id(self, backend_node_id: int) -> Element | None:
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
        
    def property(self, name: str) -> dict[str, Any]:
        """
        Busca una propiedad por su nombre y devuelve un diccionario con 
        todos sus atributos. Si no existe, devuelve valores seguros por defecto.
        """
        normalized = str(name).strip().lower() if name is not None else ""
        prop = next((p for p in self.properties if p.name == normalized), None)
        
        return {
            "name": prop.name if prop is not None else "",
            "before_value": prop.before_value if prop is not None and prop.before_value is not None else "",
            "after_value": prop.after_value if prop is not None else None,
            "token_value": prop.token_value if prop is not None else None,
            "has_color": prop.has_color if prop is not None else False,
            "in_css": prop.in_css if prop is not None else False,
            "current_value": prop.current_value if prop is not None else "",
            "has_changed": prop.has_changed if prop is not None else False
        }

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
        color: str,
        background_colors: Iterable[str],
        font_size: Any,
        font_weight: Any,
    ) -> tuple[str, Color, float, float, bool] | None:
        background_values = tuple(background_colors or ())
        if not color or not background_values:
            print(str(color))
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
            print(str(font_size))
            return None

        font_weight = get_font_weight(str(font_weight)) or 400
        is_large_text = (
            font_size >= 24
            or font_size >= 56 / 3 and font_weight >= 700
        )
        required_ratio = 3.0 if is_large_text else 4.5

        return (
            foreground.convert("srgb").to_string(comma=True, alpha=True, rounding="decimal", precision=0),
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
        for property_name in ("fill", "background", "background-image", "background-color"):
            # Almacenamos el diccionario de la propiedad una sola vez para mejorar rendimiento
            prop = self.property(property_name)
            prop_value = prop["current_value"]  # Coincide exactamente con tu nueva clave

            match prop["name"]:
                case "background":
                    bg_image_name = self.property("background-image")["name"]
                    
                    if self.has_image and bg_image_name != "":
                        continue
                    return prop

                case "fill":
                    if self.tag_name in SVG_PAINT_TAGS and get_colors(prop_value) is not None and not are_all_colors_transparent(prop_value):
                        return prop

                case "background-image":
                    # Usamos las banderas booleanas seguras de tu propio diccionario
                    if (not self.has_image and not prop["has_color"]) or (prop["has_color"] and are_all_colors_transparent(prop_value)):
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
        for ancestor in root.ancestors_of(self):
            if ancestor.tag_name == "body" or ancestor.has_image:
                return ancestor
                
            bg_prop = ancestor.effective_background
            bg_value = bg_prop["current_value"]

            if bg_prop["name"] and ancestor.tag_name not in SVG_PAINT_TAGS and get_colors(bg_value) is not None and not are_all_colors_transparent(bg_value):
                    return ancestor

        # Retorno de cortocircuito seguro si ningún ancestro aportó color
        return root

def iter_elements(root: Element | None) -> Iterable[Element]:
    return () if root is None else root.iter_dfs()
