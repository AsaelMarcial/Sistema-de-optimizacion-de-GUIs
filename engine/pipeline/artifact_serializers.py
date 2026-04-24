from __future__ import annotations

from typing import Any

from engine.domain.models.token import TokenInventoryModel


def build_token_inventory_artifact(
    token_inventory: TokenInventoryModel,
) -> dict[str, Any]:
    return token_inventory.to_dict()
