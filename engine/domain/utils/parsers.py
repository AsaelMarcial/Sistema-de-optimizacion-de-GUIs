from __future__ import annotations

from tinycss2 import parse_one_component_value, parse_component_value_list

GRADIENT_FUNCTIONS = {
    "linear-gradient",
    "radial-gradient",
    "conic-gradient",
    "repeating-linear-gradient",
    "repeating-radial-gradient",
    "repeating-conic-gradient",
}


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

    value = parse_one_component_value(
        property_value,
        skip_comments=True,
    )

    # URL sin comillas: url(imagenes/icono.svg)
    if value.type == "url":
        return bool(value.value.strip())

    # URL con comillas: url("imagenes/icono.svg")
    if value.type != "function" or value.lower_name != "url":
        return False

    arguments = [
        token
        for token in value.arguments
        if token.type not in {"whitespace", "comment"}
    ]

    return (
        len(arguments) == 1
        and arguments[0].type == "string"
        and bool(arguments[0].value.strip())
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