from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PipelineResult:
    payload: dict[str, Any] | None
    error: str | None = None

    def to_tuple(self) -> tuple[dict[str, Any] | None, str | None]:
        return self.payload, self.error
