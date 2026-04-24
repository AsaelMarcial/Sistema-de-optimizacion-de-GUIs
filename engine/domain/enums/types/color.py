from __future__ import annotations

from enum import StrEnum


class ColorFamilyType(StrEnum):
    ACHROMATIC = "achromatic"
    CHROMATIC = "chromatic"


class ColorConfirmationStatus(StrEnum):
    SEMANTIC_ONLY = "semantic_only"
    CONFIRMED = "confirmed"


class ObservedColorRole(StrEnum):
    TEXT = "text"
    BACKGROUND = "background"
    BORDER = "border"
    FILL = "fill"
    STROKE = "stroke"
    OTHER = "other"


class PaletteRoleBias(StrEnum):
    BACKGROUND = "background"
    FOREGROUND = "foreground"
    OTHER = "other"
    MIXED = "mixed"
