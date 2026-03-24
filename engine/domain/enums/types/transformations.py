from __future__ import annotations

from enum import StrEnum


class TransformationKind(StrEnum):
    HEURISTIC = "heuristic"


class TransformationStatus(StrEnum):
    APPLIED = "applied"
    SKIPPED = "skipped"
