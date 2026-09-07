from __future__ import annotations

from typing import Literal, NamedTuple
from urllib.parse import unquote, urlsplit

from coloraide import Color
from tinycss2 import parse_component_value_list, serialize
from tinycss2.ast import (
    DimensionToken,
    FunctionBlock,
    NumberToken,
    PercentageToken,
    URLToken,
    WhitespaceToken,
)

COLOR = "color"
PATH = "path"
URL = "url"
SIZE = "size"
OTHER = "other"
TokenType = Literal["color", "path", "url", "size", "other"]

class Value(NamedTuple):
    type: TokenType
    value: str | Color
    line: int
    column: int


def classify_value(value: str) -> tuple[Value, ...]:
    result: list[Value] = []

    for token in parse_component_value_list(
        str(value or ""),
        skip_comments=True,
    ):
        if isinstance(token, WhitespaceToken):
            continue

        type_: TokenType = OTHER
        value_ = token.serialize().strip()

        if (
            isinstance(token, URLToken)
            or isinstance(token, FunctionBlock)
            and token.name.lower() == "url"
        ):
            url_value = (
                token.value
                if isinstance(token, URLToken)
                else serialize(token.arguments).strip("'\"")
            )
            parsed_url = urlsplit(unquote(url_value))

            if (
                parsed_url.scheme in {"http", "https"}
                and parsed_url.hostname not in {"localhost", "127.0.0.1"}
            ):
                type_ = URL
                value_ = url_value
            else:
                type_ = PATH
                value_ = parsed_url.path or url_value

        elif Color.match(value_):
            type_ = COLOR
            value_ = Color(value_).convert("srgb")

        elif isinstance(token, (DimensionToken, NumberToken, PercentageToken)):
            type_ = SIZE

        result.append(
            Value(
                type_,
                value_,
                token.source_line,
                token.source_column,
            )
        )

    return tuple(result)
