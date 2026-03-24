from __future__ import annotations

from enum import StrEnum


class ColorFamilyType(StrEnum):
    ACHROMATIC = "achromatic"
    CHROMATIC = "chromatic"


class ColorConfirmationStatus(StrEnum):
    SEMANTIC_ONLY = "semantic_only"
    CONFIRMED = "confirmed"


class PaletteRoleBias(StrEnum):
    BACKGROUND = "background"
    FOREGROUND = "foreground"
    OTHER = "other"
    MIXED = "mixed"
