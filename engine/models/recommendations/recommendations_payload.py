from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RecommendationsPayload:
    items: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": list(self.items),
            "summary": self.summary,
        }
