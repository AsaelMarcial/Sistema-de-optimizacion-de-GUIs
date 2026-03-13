"""Scope registries for CSS properties and HTML elements."""

from engine.enums.scope.css_properties import (
    CSS_PROPERTIES_BY_ID,
    CSS_PROPERTY_COMPUTED_ALIASES,
    CSS_PROPERTY_SHORTHANDS,
    CssPropertyCategory,
    CssPropertyId,
    CssPropertySpec,
    get_in_scope_css_properties,
)
from engine.enums.scope.html_elements import (
    HTML_ELEMENTS_BY_ID,
    HtmlElementId,
    HtmlElementScopeGroup,
    HtmlElementSpec,
    get_snapshot_included_html_elements,
)

__all__ = [
    "CSS_PROPERTIES_BY_ID",
    "CSS_PROPERTY_COMPUTED_ALIASES",
    "CSS_PROPERTY_SHORTHANDS",
    "CssPropertyCategory",
    "CssPropertyId",
    "CssPropertySpec",
    "HTML_ELEMENTS_BY_ID",
    "HtmlElementId",
    "HtmlElementScopeGroup",
    "HtmlElementSpec",
    "get_in_scope_css_properties",
    "get_snapshot_included_html_elements",
]
