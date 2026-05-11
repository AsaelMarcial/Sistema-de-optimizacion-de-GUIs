from __future__ import annotations

from enum import StrEnum


class ElementSourceKind(StrEnum):
    OWN = "own"
    INHERITED = "inherited"


class PropertyClassification(StrEnum):
    BACKGROUND = "background"
    FOREGROUND = "foreground"
    EFFECT = "effect"
    OTHER = "other"
