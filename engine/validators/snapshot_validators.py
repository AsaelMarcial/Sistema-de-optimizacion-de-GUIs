from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def has_snapshot_structure(payload: Any) -> bool:
    if hasattr(payload, "metadata") and hasattr(payload, "nodes"):
        return True
    if not isinstance(payload, Mapping):
        return False
    return "metadata" in payload and ("nodes" in payload or "document" in payload)
