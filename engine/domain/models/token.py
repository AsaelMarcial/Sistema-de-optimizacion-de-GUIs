from __future__ import annotations

from dataclasses import dataclass
from engine.domain.models.color_scheme import Color, Palette
from engine.domain.models.element import Element, Property


@dataclass(frozen=True, slots=True)
class RootToken:
    """
    Representa un token raíz que contiene un valor real (por ejemplo, un color).
    Ejemplo:
        token_id -> "blue-500"
        value = "#4285F4"
        
    """
    token_id: str
    value: Color

    @property
    def palette(self) -> str:
        """Indica el nombre de la paleta a la que pertenece."""
        return self.token_id.rsplit("-", 1)[0]

    @property
    def tone(self) -> str:
        """Indica el tone_value del Tone al que pertenece."""
        return self.token_id.rsplit("-", 1)[1]

@dataclass(slots=True)
class PropertyToken:
    """
    Representa una propiedad de un elemento, su value fuera de los data-theme (var(token-id) y sus values en los data-themes (token-id = glow_theme_value)).
    """
    token_id: str
    glow_theme_value: str
    original_theme_value: str

class TokenInventory:

    def __init__(self) -> None:

        self.root_tokens: dict[str, RootToken] = {}
        self.property_tokens: dict[str, PropertyToken] = {}

    # ==========================================================
    # CREATE
    # ==========================================================
    
    @staticmethod
    def create_token_name(terms: list[str]) -> str:
        normalized_terms = [
            term.strip()
            for term in terms
            if isinstance(term, str)
        ]

        if not normalized_terms:
            raise ValueError("El token debe contener al menos un término válido.")

        return f"--{'-'.join(normalized_terms)}"

    def _generate_property_token_variant(self, name: str) -> int:
        """Busca el valor más grande de 'variant' en self.property_tokens de los PropertyToken que tienen 
        los valores de sus atributos identicos a los valores de los argumentos.
        
        Devuelve 0 si no encuentra ninguno.
        """
        # .values() accede directamente a los objetos PropertyToken
        # default=0 evita errores si el diccionario está vacíoseparate_token_terms(self.name)[0]
        variant = 0
        for token in self.property_tokens.values():
            token_name, _, token_variant = token.token_id.rpartition("-")
            if token_name != name:
                continue

            try:
                variant = max(variant, int(token_variant))
            except ValueError:
                continue

        return variant + 1

    def create_root_token(
        self,
        tone_name: str,
        value: Color,
    ) -> RootToken:
        name = self.create_token_name([tone_name])
        # Buscar si ya existe uno idéntico.
        if self.root_token(name) is not None:
            return self.root_token(name)

        self.root_tokens[name] = RootToken(
            token_id= name,
            value=value.convert("srgb").to_string(comma=True, alpha=True, rounding="decimal", precision=0),
        )

        return self.root_tokens[name]

    def create_property_token(
        self,
        category: str,
        property_name: str,
        glow_theme_value: str,
        original_theme_value: str
    ) -> PropertyToken:

        for token in self.property_tokens.values():
            if (token.glow_theme_value == glow_theme_value or token.original_theme_value == original_theme_value):
                return token

        name = self.create_token_name([category, property_name])
        variant= self._generate_property_token_variant(name)
        
        token = PropertyToken(
            token_id = f"{name}-{variant}",
            glow_theme_value = glow_theme_value,
            original_theme_value = original_theme_value
        )

        self.property_tokens[token.token_id] = token

        return token

    # ==========================================================
    # DEFAULT TOKENS GENERATORS
    # ==========================================================

    def generate_root_tokens(self, palettes: dict[str, Palette]) -> dict[str, RootToken]:
        for palette in palettes.values():
            for tone in palette.tones:
                self.create_root_token(tone.name, tone.color)
        
        return self.root_tokens

    def generate_property_tokens(self, root: Element) -> dict[str, PropertyToken]:
        for element in root.iter_bfs():
            for property in element.properties:
                if property.name is not None and property.has_color and element.tag_name != "#text":
                    if property.after_value is None:
                        self.create_property_token(element.category, property.name, property.before_value, property.before_value)
                    elif property.before_value is None:
                        self.create_property_token(element.category, property.name, property.after_value, property.after_value)
                    elif property.before_value is not None and property.after_value is not None:
                        self.create_property_token(element.category, property.name, property.after_value, property.before_value)
                else:
                    continue
        
        return self.property_tokens

    # ==========================================================
    # GET
    # ==========================================================

    def root_token(self, token_id: str) -> RootToken | None:
        return self.root_tokens.get(token_id) or None

    def property_token(self, token_id: str) -> PropertyToken | None:
        return self.property_tokens.get(token_id) or None
