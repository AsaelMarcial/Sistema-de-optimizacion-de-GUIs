from __future__ import annotations

from tinycss2 import parse_one_component_value, parse_component_value_list, serialize
from copy import deepcopy
from urllib.parse import urlsplit

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

def is_gradient(property_value: str) -> bool:
    if not isinstance(property_value, str) or not property_value.strip():
        return False

    value = parse_one_component_value(
        property_value,
        skip_comments=True,
    )

    if (
        value.type != "function"
        or value.lower_name not in GRADIENT_FUNCTIONS
    ):
        return False

    arguments = [
        token
        for token in value.arguments
        if token.type not in {"whitespace", "comment"}
    ]

    return (
        bool(arguments)
        and not any(token.type == "error" for token in arguments)
        and any(
            token.type == "literal" and token.value == ","
            for token in arguments
        )
    )

def is_url_image(property_value: str) -> bool:
    if not isinstance(property_value, str) or not property_value.strip():
        return False

    raw_value = property_value.strip()
    parsed_value = parse_one_component_value(
        raw_value,
        skip_comments=True,
    )

    if parsed_value.type == "url":
        image_url = parsed_value.value.strip()

    elif parsed_value.type == "function" and parsed_value.lower_name == "url":
        arguments = [
            token
            for token in parsed_value.arguments
            if token.type not in {"whitespace", "comment"}
        ]

        if len(arguments) != 1 or arguments[0].type != "string":
            return False

        image_url = arguments[0].value.strip()

    else:
        # Ruta o URL directa, sin url(...)
        image_url = raw_value.strip("\"'")

    if not image_url:
        return False

    image_path = urlsplit(image_url).path.lower()

    return image_path.endswith(_IMAGE_EXTENSIONS)

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
                    match.color.set("alpha", 1),
                )
            )

        start = max(match.end, start + 1)

    return colors or None

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

def separate_token_terms(value: str) -> list:
    """Función auxiliar para limpiar los guiones y separar por puntos."""
    return value.removeprefix("--").split(".")
