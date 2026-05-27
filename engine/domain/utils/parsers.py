from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from itertools import zip_longest
from typing import Any

Missing = object()
Condition = Callable[[Any], bool]
KeyFunction = Callable[[Any], Any]


def get_value(element: Any, key: str | int, default: Any = None) -> Any:
    if isinstance(element, Mapping):
        return element.get(key, default)

    if isinstance(key, int) and isinstance(element, Sequence) and not isinstance(
        element,
        (str, bytes, bytearray),
    ):
        return element[key] if -len(element) <= key < len(element) else default

    if isinstance(key, str):
        return getattr(element, key, default)

    return default


def resolve_value(
    source: Any,
    path: str | Sequence[str | int],
    default: Any = None,
) -> Any:
    keys = (
        tuple(_coerce_path_key(part) for part in path.split("."))
        if isinstance(path, str)
        else path
    )
    current = source
    for key in keys:
        current = get_value(current, key, Missing)
        if current is Missing:
            return default
    return current


def _coerce_path_key(value: str) -> str | int:
    stripped = value.strip()
    return int(stripped) if stripped.lstrip("-").isdigit() else stripped


def flatten_list(
    nested_list: list[Any] | dict[str, Any],
    attributes: list[str],
    depth: int = 0,
    _attr_index: int = 0,
) -> Iterator[list[Any]]:
    if _attr_index >= len(attributes):
        return

    source_items = nested_list if isinstance(nested_list, list) else [nested_list]
    attribute = attributes[_attr_index]
    result: list[Any] = []

    for element in source_items:
        value = get_value(element, attribute)
        if value is None:
            continue
        if not isinstance(value, list):
            result.append(value)
            continue

        pending: list[tuple[Any, int]] = [(item, depth) for item in reversed(value)]
        while pending:
            item, current_depth = pending.pop()
            if isinstance(item, list) and current_depth > 0:
                pending.extend(
                    (sub_item, current_depth - 1)
                    for sub_item in reversed(item)
                )
            else:
                result.append(item)

    yield result
    yield from flatten_list(
        nested_list=nested_list,
        attributes=attributes,
        depth=depth,
        _attr_index=_attr_index + 1,
    )


def resolve_index_map(items: Iterable[Any]) -> dict[Any, int]:
    return {value: index for index, value in enumerate(items)}


def resolve_pairs(
    keys: Iterable[Any],
    values: Iterable[Any],
    fill_value: Any = None,
) -> Iterator[tuple[Any, Any]]:
    for key, value in zip_longest(keys, values, fillvalue=fill_value):
        if key is fill_value:
            continue
        yield key, value


def filter_items(items: Iterable[Any], condition: Condition) -> list[Any]:
    return [item for item in items if check_content(item, condition)]


def group_by(
    items: Iterable[Any],
    key: str | int | KeyFunction,
) -> dict[Any, list[Any]]:
    grouped: dict[Any, list[Any]] = {}
    for item in items:
        group_key = key(item) if callable(key) else get_value(item, key)
        grouped.setdefault(group_key, []).append(item)
    return grouped


def check_content(item: Any, condition: Condition) -> bool:
    try:
        return bool(condition(item))
    except (KeyError, IndexError, TypeError, AttributeError, ValueError):
        return False


def attr_equals(key: str | int, expected: Any) -> Condition:
    return lambda item: get_value(item, key, Missing) == expected


def attr_in(
    key: str | int,
    expected_values: set[Any] | tuple[Any, ...] | list[Any],
) -> Condition:
    return lambda item: get_value(item, key, Missing) in expected_values


def attr_not_none(key: str | int) -> Condition:
    return lambda item: get_value(item, key, Missing) is not None


def all_conditions(*conditions: Condition) -> Condition:
    return lambda item: all(check_content(item, condition) for condition in conditions)


def any_condition(*conditions: Condition) -> Condition:
    return lambda item: any(check_content(item, condition) for condition in conditions)
