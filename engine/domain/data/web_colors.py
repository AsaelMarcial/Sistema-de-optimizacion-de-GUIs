from __future__ import annotations

"""Canonical web-color data and helper accessors exposed to the domain layer."""

from workspace.generated_web_colors import (  # type: ignore[attr-defined]
    MultiValueEnum,
    WebColor as _GeneratedWebColor,
    WebColorGroup,
    WebColorMatch,
    get_web_color as _generated_get_web_color,
    iter_web_colors as _generated_iter_web_colors,
    nearest_web_color as _generated_nearest_web_color,
)


WebColor = _GeneratedWebColor


def _display_name(self: WebColor) -> str:
    html_names = tuple(getattr(self, "html_names", ()) or ())
    if html_names:
        return str(html_names[0])
    canonical_name = str(getattr(self, "canonical_name", self.name.lower()))
    return " ".join(part.capitalize() for part in canonical_name.replace("_", " ").split())


def _hex_value(self: WebColor) -> str:
    return str(getattr(self, "hex_code"))


def _wikipedia_family(self: WebColor) -> str:
    group = getattr(self, "group")
    return str(getattr(group, "value", group))


def _value_map(self: WebColor) -> dict[str, object]:
    return {
        "canonical_name": getattr(self, "canonical_name"),
        "display_name": self.display_name,
        "html_names": tuple(getattr(self, "html_names", ()) or ()),
        "group": self.wikipedia_family,
        "hex": self.hex_value,
        "rgb": tuple(getattr(self, "rgb")),
        "hsl": tuple(getattr(self, "hsl")),
        "hsv": tuple(getattr(self, "hsv")),
    }


if not hasattr(WebColor, "display_name"):
    WebColor.display_name = property(_display_name)  # type: ignore[attr-defined]

if not hasattr(WebColor, "hex_value"):
    WebColor.hex_value = property(_hex_value)  # type: ignore[attr-defined]

if not hasattr(WebColor, "wikipedia_family"):
    WebColor.wikipedia_family = property(_wikipedia_family)  # type: ignore[attr-defined]

if not hasattr(WebColor, "value_map"):
    WebColor.value_map = property(_value_map)  # type: ignore[attr-defined]


if not hasattr(WebColorMatch, "wikipedia_family"):
    WebColorMatch.wikipedia_family = property(  # type: ignore[attr-defined]
        lambda self: str(getattr(self, "group_name"))
    )


if not hasattr(WebColorMatch, "hex_value"):
    WebColorMatch.hex_value = property(  # type: ignore[attr-defined]
        lambda self: f"#{str(getattr(self, 'hex_code')).lower().lstrip('#')}"
    )


def iter_web_colors(group: WebColorGroup | str | None = None):
    if isinstance(group, str):
        for group_member in WebColorGroup:
            if group_member.value == group or group_member.name == group.upper():
                group = group_member
                break
    return _generated_iter_web_colors(group=group)


def get_web_color(value):
    return _generated_get_web_color(value)


def nearest_web_color(value, *, method: str = "2000") -> WebColorMatch:
    return _generated_nearest_web_color(value, method=method)


__all__ = [
    "MultiValueEnum",
    "WebColor",
    "WebColorGroup",
    "WebColorMatch",
    "get_web_color",
    "iter_web_colors",
    "nearest_web_color",
]
