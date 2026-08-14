from __future__ import annotations

from dataclasses import dataclass, field
from engine.domain.models.element import Element


@dataclass(slots=True)
class PropertyToken:
    """
    Representa una propiedad de un elemento, su value fuera de los data-theme (var(token-id) y sus values en los data-themes (token-id = glow_theme_value)).
    """
    token_id: str
    glow_theme_value: str
    original_theme_value: str
    element_ids: set[tuple[int, str]] = field(default_factory=set[tuple[int, str]])

    @property
    def to_var(self) -> str:
        return f"var({self.token_id})"

class TokenInventory:

    def __init__(self) -> None:

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

    def create_property_token(
        self,
        category: str,
        property_name: str,
        glow_theme_value: str,
        original_theme_value: str
    ) -> PropertyToken:

        for token in self.property_tokens.values():
            if (token.glow_theme_value == glow_theme_value and token.original_theme_value == original_theme_value):
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

    def generate_property_tokens(self, root: Element) -> dict[str, PropertyToken]:
        for element in root.iter_dfs():
            for property in element.properties:
                if property.calculated_value is not None and property.type in ("inline", "matched"):
                    created_token = self.create_property_token(
                        element.category,
                        property.name,
                        str(property.calculated_value),
                        property.before_value,
                    )
                    created_token.element_ids.add((element.node_id, property.name))
                else:
                    continue
        
        return self.property_tokens

    # ==========================================================
    # GET
    # ==========================================================

    def property_token(self, token_id: str) -> PropertyToken | None:
        return self.property_tokens.get(token_id) or None
