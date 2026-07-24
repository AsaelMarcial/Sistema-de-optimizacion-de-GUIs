from __future__ import annotations

from dataclasses import dataclass
from logging import root
from engine.domain.models.color_scheme import Color, Palette
from engine.domain.data.tokens import THEMETOKEN_DEFAULTS, ACHROMATIC_THEMETOKEN_VARIANTS, CHROMATIC_THEMETOKEN_VARIANTS


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
    def palette(self) -> bool:
        """Indica el nombre de la paleta a la que pertenece."""
        return self.rsplit("-", 1)[0]

    @property
    def tone(self) -> bool:
        """Indica el tone_value del Tone al que pertenece."""
        return self.rsplit("-", 1)[1]

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
    
    def create_token_name(terms: list[str]) -> str:
        normalized_terms = [
            term.strip()
            for term in terms
            if isinstance(term, str)
        ]

        if not normalized_terms:
            "El token debe contener al menos un término válido."

        return f"--{'-'.join(normalized_terms)}"

    def _generate_property_token_variant(self, name: str) -> int:
        """Busca el valor más grande de 'variant' en self.property_tokens de los PropertyToken que tienen 
        los valores de sus atributos identicos a los valores de los argumentos.
        
        Devuelve 0 si no encuentra ninguno.
        """
        # .values() accede directamente a los objetos PropertyToken
        # default=0 evita errores si el diccionario está vacíoseparate_token_terms(self.name)[0]
        return max(
            (int(token.token_id.split()[-1]) 
            for token in self.property_tokens.values() 
            if token.token_id.rsplit("-", 1)[0] == name), 
            default=0
        ) + 1

    def create_root_token(
        self,
        tone_name: str,
        value: Color,
    ) -> RootToken:
        name = self.create_property_token(tone_name)
        # Buscar si ya existe uno idéntico.
        if self.root_token(name) is not None:
            return self.root_token(name)

        self.root_tokens[name] = RootToken(
            token_id= name,
            value=value,
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

        name = self.create_token_name(category, property_name)
        variant= self._generate_property_token_variant(name)
        
        token = PropertyToken(
            token_id = "-".join(name, variant),
            glow_theme_value = glow_theme_value,
            original_theme_value = original_theme_value
        )

        self.root_tokens[token.token_id] = token

        return token

    # ==========================================================
    # DEFAULT TOKENS GENERATORS
    # ==========================================================

    def generate_root_tokens(self, palettes: list[Palette]) -> dict[str, RootToken]:
        for palette in palettes:
            for tone in palette.tones:
                self.create_root_token(tone.name, tone.color)
        
        return self.root_tokens

    # ==========================================================
    # GET
    # ==========================================================

    def root_token(self, token_id: str) -> RootToken | None:
        return self.root_tokens_tokens.get(token_id) or None

    def property_token(self, token_id: str) -> PropertyToken | None:
        return self.property_tokens.get(token_id) or None
