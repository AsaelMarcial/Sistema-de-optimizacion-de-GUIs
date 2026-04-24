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
