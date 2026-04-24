from __future__ import annotations

from typing import Any


def has_inventory_entries(payload: Any) -> bool:
    return hasattr(payload, "__len__") and len(payload) >= 0
