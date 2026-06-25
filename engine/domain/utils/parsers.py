from __future__ import annotations

from tinycss2 import parse_one_component_value, parse_component_value_list, serialize
from copy import deepcopy

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