from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List
import time

@dataclass
class DebugTrace:
    enabled: bool = True
    started_at: float = field(default_factory=time.time)
    steps: List[Dict[str, Any]] = field(default_factory=list)

    def add_step(self, name: str, data: Dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        self.steps.append({
            "t": round(time.time() - self.started_at, 4),
            "step": name,
            "data": data or {}
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "started_at": self.started_at,
            "steps": self.steps
        }
