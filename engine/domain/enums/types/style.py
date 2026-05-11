from __future__ import annotations

from enum import StrEnum


class StyleSourceKind(StrEnum):
    INLINE = "inline"
    EMBEDDED = "embedded"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class RuleType(StrEnum):
    STYLE = "style"
    MEDIA = "media"
    SUPPORTS = "supports"
    LAYER = "layer"
    CONTAINER = "container"
    SCOPE = "scope"
    KEYFRAMES = "keyframes"
    FONT_FACE = "font-face"
    PAGE = "page"
    IMPORT = "import"
    UNKNOWN = "unknown"


class DeclarationSyntax(StrEnum):
    LONGHAND = "longhand"
    SHORTHAND = "shorthand"
    CUSTOM_PROPERTY = "custom-property"
