from __future__ import annotations

from enum import StrEnum


class StyleKind(StrEnum):
    COMPUTED = "computed"
    INLINE = "inline"
    EMBEDDED = "embedded"
    EXTERNAL = "external"
    INHERITED = "inherited"
    USER_AGENT = "user-agent"


class StyleOrigin(StrEnum):
    AUTHOR = "author"
    USER = "user"
    USER_AGENT = "user-agent"


class StyleUsageStatus(StrEnum):
    UNKNOWN = "unknown"
    USED = "used"


class StyleResolutionStatus(StrEnum):
    EXACT_MATCH = "exact_match"
    AMBIGUOUS_MATCH = "ambiguous_match"
    UNRESOLVED = "unresolved"


class RuleOrigin(StrEnum):
    INLINE = "inline"
    EMBEDDED = "embedded"
    EXTERNAL = "external"
    USER_AGENT = "user-agent"


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
