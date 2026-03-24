from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def has_color_frequency_rows(payload: Any) -> bool:
    if not isinstance(payload, Sequence):
        return False
    for item in payload:
        if not hasattr(item, "get"):
            return False
        if item.get("color") is None or item.get("count") is None:
            return False
    return True


def has_inventory_entries(payload: Any) -> bool:
    return hasattr(payload, "__len__") and len(payload) >= 0
