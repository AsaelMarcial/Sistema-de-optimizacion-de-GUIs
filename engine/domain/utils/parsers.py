from __future__ import annotations
from ast import unparse

from tinycss2 import parse_component_value_list, serialize, parse_declaration_list
from copy import deepcopy
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import xml.etree.ElementTree as ET
import re

from engine.domain.models.color_scheme import Color

GRADIENT_FUNCTIONS = {
    "linear-gradient",
    "radial-gradient",
    "conic-gradient",
    "repeating-linear-gradient",
    "repeating-radial-gradient",
    "repeating-conic-gradient",
}

_IMAGE_EXTENSIONS = (
    ".avif",
    ".bmp",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
)

def has_gradient(property_value: str) -> bool:
    if not isinstance(property_value, str) or not property_value.strip():
        return False

    tokens = parse_component_value_list(
        property_value,
        skip_comments=True,
    )

    pending = list(tokens)
    while pending:
        token = pending.pop()
        if token.type == "function":
            if token.lower_name in GRADIENT_FUNCTIONS:
                arguments = [
                    argument
                    for argument in token.arguments
                    if argument.type not in {"whitespace", "comment"}
                ]
                return (
                    bool(arguments)
                    and not any(argument.type == "error" for argument in arguments)
                    and any(
                        argument.type == "literal" and argument.value == ","
                        for argument in arguments
                    )
                )
            pending.extend(token.arguments)
        elif hasattr(token, "content"):
            pending.extend(token.content)

    return False

def has_url_image(property_value: str) -> bool:
    if not isinstance(property_value, str) or not property_value.strip():
        return False

    raw_value = property_value.strip()
    tokens = parse_component_value_list(
        raw_value,
        skip_comments=True,
    )
    pending = list(tokens)

    while pending:
        token = pending.pop()
        image_url = None

        if token.type == "url":
            image_url = token.value.strip()
        elif token.type == "function":
            if token.lower_name == "url":
                arguments = [
                    argument
                    for argument in token.arguments
                    if argument.type not in {"whitespace", "comment"}
                ]
                if len(arguments) == 1 and arguments[0].type == "string":
                    image_url = arguments[0].value.strip()
            else:
                pending.extend(token.arguments)
        elif hasattr(token, "content"):
            pending.extend(token.content)

        if image_url and urlsplit(image_url).path.lower().endswith(_IMAGE_EXTENSIONS):
            return True

    return urlsplit(raw_value.strip("\"'")).path.lower().endswith(_IMAGE_EXTENSIONS)

def extract_url_value(value: str) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None

    text = value.strip()
    match = re.search(r"url\(\s*(['\"]?)(.*?)\1\s*\)", text, re.IGNORECASE)
    if match:
        return match.group(2).strip()

    return text.strip("\"'")

def cache_busted_url(value: str, version: str) -> str:
    url = extract_url_value(value) or value
    parts = urlsplit(url)
    query = [
        (key, query_value)
        for key, query_value in parse_qsl(parts.query, keep_blank_values=True)
        if key != "glow"
    ]
    key, _, query_value = version.partition("=")
    query.append((key, query_value))
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )

def has_multiplevalues(property_value: str) -> bool:
    if not isinstance(property_value, str) or not property_value.strip():
        return False

    tokens = parse_component_value_list(
        property_value,
        skip_comments=True,
    )

    if any(token.type == "error" for token in tokens):
        return False

    values = [
        token
        for token in tokens
        if token.type != "whitespace"
        and not (
            token.type == "literal"
            and token.value in {",", "/"}
        )
    ]

    return len(values) > 1

def get_colors(value: str) -> list[tuple[str, Color]] | None:
    if not isinstance(value, str) or not value:
        return None

    colors: list[tuple[str, Color]] = []
    start = 0

    while start < len(value):
        match = Color.match(value, start=start, fullmatch=False)

        if match is None:
            start += 1
            continue

        if match.color:
            colors.append(
                (
                    value[match.start:match.end],
                    match.color,
                )
            )

        start = max(match.end, start + 1)

    return colors or None

def are_all_colors_transparent(css_text: str) -> bool:
    """
    Checks if all colors in the given text are completely transparent.
    Reuses the custom get_colors function.
    """
    # Obtenemos la lista de tuplas (texto_color, objeto_color) de tu función.
    # Si devuelve None o una lista vacía, usamos el cortocircuito 'or []' para evitar errores.
    detected_colors = get_colors(css_text) or []
    if not detected_colors:
        return False
    
    # all() devuelve True si CADA UNO de los colores cumple que su alfa es exactamente 0.0.
    # Si la lista está vacía, all() devuelve True automáticamente (verdad vacua).
    return all(color.alpha(nans=False) == 0.0 for _, color in detected_colors)

def are_all_colors_equal(css_text: str) -> bool:
    """
    Returns True if all colors detected in the text are identical 
    according to ColorAide's mathematical comparison.
    Returns True if 0 or 1 colors are found (trivially equal).
    """
    # Usamos tu función get_colors. Si da None, el cortocircuito 'or []' evita errores.
    detected_colors = get_colors(css_text) or []
    
    # Si solo hay uno, técnicamente todos son iguales entre sí
    if not detected_colors:
        return False
        
    # Tomamos el primer objeto Color como nuestra referencia de comparación
    _, reference_color = detected_colors[0]
    
    # Comparamos todos los demás colores contra la referencia usando delta_e
    # Si la diferencia (Delta E) con respecto al primero es 0.0, son idénticos
    return all(reference_color.delta_e(color) == 0.0 for _, color in detected_colors)

def replace_property_values(
    property_value: str,
    old_values: list[str],
    new_values: list[str],
) -> str:
    if not isinstance(property_value, str):
        raise TypeError("property_value debe ser un string.")

    if len(old_values) != len(new_values):
        raise ValueError(
            "old_values y new_values deben tener la misma longitud."
        )

    tokens = parse_component_value_list(
        property_value,
        skip_comments=False,
    )

    replacements = []

    for old_value, new_value in zip(old_values, new_values):
        old_tokens = parse_component_value_list(
            old_value,
            skip_comments=False,
        )
        new_tokens = parse_component_value_list(
            new_value,
            skip_comments=False,
        )

        if not old_tokens or not new_tokens:
            raise ValueError(
                "Los valores viejos y nuevos no pueden estar vacíos."
            )

        if any(
            token.type == "error"
            for token in [*old_tokens, *new_tokens]
        ):
            raise ValueError(
                f"Valor CSS inválido: {old_value!r} o {new_value!r}."
            )

        replacements.append(
            (
                serialize(old_tokens),
                len(old_tokens),
                new_tokens,
            )
        )

    # Prioriza los valores formados por más tokens.
    replacements.sort(
        key=lambda replacement: replacement[1],
        reverse=True,
    )

    token_lists = [tokens]

    while token_lists:
        current_tokens = token_lists.pop()
        index = 0

        while index < len(current_tokens):
            for old_text, old_length, new_tokens in replacements:
                candidate = current_tokens[
                    index:index + old_length
                ]

                if (
                    len(candidate) == old_length
                    and serialize(candidate) == old_text
                ):
                    current_tokens[
                        index:index + old_length
                    ] = deepcopy(new_tokens)

                    index += len(new_tokens)
                    break
            else:
                token = current_tokens[index]

                # Revisa valores dentro de funciones:
                # linear-gradient(), rgb(), var(), etc.
                if token.type == "function":
                    token_lists.append(token.arguments)

                # Revisa bloques (), [] y {}.
                elif hasattr(token, "content"):
                    token_lists.append(token.content)

                index += 1

    return serialize(tokens)

def matches_default_value(
    property_value: str,
    default_values: list[str | None] | str | None,
) -> bool:
    if default_values is None:
        return False

    if isinstance(default_values, str):
        default_values = [default_values]

    property_tokens = {
        serialize([token]).strip().casefold()
        for token in parse_component_value_list(
            property_value,
            skip_comments=True,
        )
        if token.type != "whitespace"
    }

    for default_value in default_values:
        if default_value is None:
            continue

        default_tokens = [
            token
            for token in parse_component_value_list(
                default_value,
                skip_comments=True,
            )
            if token.type != "whitespace"
        ]

        # Cada miembro de default_values debe representar un solo token.
        if len(default_tokens) != 1:
            continue

        normalized_default = (
            serialize([default_tokens[0]])
            .strip()
            .casefold()
        )

        if normalized_default in property_tokens:
            return True

    return False

def has_important_flag(value_text: str) -> bool:
    """
    Parses a CSS value string using tinycss2 to robustly check 
    if it contains the !important flag, ignoring format variations.
    """
    # Simulamos una propiedad ficticia 'x:' seguida del valor a evaluar
    dummy_declaration = f"x: {value_text}"
    
    # Parseamos la línea simulada omitiendo comentarios
    declarations = parse_declaration_list(dummy_declaration, skip_comments=True)
    
    # Si la lista está vacía o el elemento no es una declaración válida, no hay bandera
    if not declarations or declarations[0].type != 'declaration':
        return False
        
    # tinycss2 evalúa la sintaxis y expone la propiedad booleana .important
    return declarations[0].important

def separate_token_terms(value: str) -> list:
    """Función auxiliar para limpiar los guiones y separar por puntos."""
    return value.removeprefix("--").split(".")

def get_file_name_and_suffix(path_or_url: str) -> tuple[str, str]:
    """
    Cleans URL syntax and splits the path from the right side 
    to safely return a tuple of (name, suffix).
    """
    clean_path = extract_url_value(path_or_url) or path_or_url
    clean_path = urlsplit(clean_path).path
    
    # 2. Dividir desde la derecha usando el punto como separador
    # maxsplit=1 asegura que maneje archivos con múltiples puntos (ej: archivo.v2.svg)
    parts = clean_path.rsplit(".", 1)
    
    # Si hay una extensión válida, devolvemos (nombre, extensión)
    if len(parts) > 1:
        return parts[0], parts[1]
        
    # Si no tiene extensión, devolvemos la ruta limpia y un sufijo vacío
    return clean_path, ""

def is_css_value_contained(value_in: str, value: str) -> bool:
    """
    Parses both CSS values into tokens and checks if the token sequence of 
    'value_in' exists sequentially inside 'value'. Case and whitespace insensitive.
    """
    if not isinstance(value_in, str) or not isinstance(value, str):
        return False

    # 1. Convertimos ambos textos en listas de tokens limpios
    # Normalizamos a minúsculas y omitimos comentarios o espacios en blanco puros
    tokens_in = [
        t for t in parse_component_value_list(value_in.lower())
        if t.type not in ('comment', 'whitespace')
    ]
    tokens_container = [
        t for t in parse_component_value_list(value.lower())
        if t.type not in ('comment', 'whitespace')
    ]

    # Si el contenedor está vacío o es más chico que lo buscado, es imposible que lo contenga
    if not tokens_container or len(tokens_in) > len(tokens_container) or not tokens_in:
        return False

    # 2. Serializamos cada token de forma individual para poder compararlos como texto
    # Esto elimina diferencias de comillas en URLs o formatos numéricos
    search_sequence = [serialize([t]).strip() for t in tokens_in]
    container_sequence = [serialize([t]).strip() for t in tokens_container]

    # 3. Buscamos la subsecuencia exacta dentro de la secuencia contenedora
    len_search = len(search_sequence)
    for i in range(len(container_sequence) - len_search + 1):
        if container_sequence[i : i + len_search] == search_sequence:
            return True

    return False
