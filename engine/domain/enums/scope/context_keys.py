from __future__ import annotations

from enum import StrEnum


class ContextRoot(StrEnum):
    SESSION = "session"
    PAGE_BUILDER = "page_builder"
    DOM = "dom"
    SCHEME = "scheme"
    SUMMARY = "summary"
    STYLE = "style"
    TOKEN = "token"
    DERIVED = "derived"
    ENVIRONMENTAL = "environmental"
    TRANSFORMATION = "transformation"
    RECOMMENDATIONS = "recommendations"
    RESULTS = "results"


class ContextKey(StrEnum):
    SESSION = "session"
    PAGE_BUILDER = "page_builder"
    DOM_TREE = "dom.tree"
    COLOR_SCHEME = "scheme.color_scheme"
    SUMMARY = "summary"
    SCHEME_COLOR_HISTOGRAM = "scheme.color_histogram"
    STYLE_CATALOG = "style.catalog"
    TOKEN_INVENTORY = "token.inventory"
    DERIVED_CONTRAST_REPORT = "derived.contrast_report"
    ENVIRONMENTAL_BEFORE_COLOR_HISTOGRAM = "environmental.before.color_histogram"
    ENVIRONMENTAL_BEFORE_ASSESSMENT = "environmental.before.assessment"
    ENVIRONMENTAL_AFTER_COLOR_HISTOGRAM = "environmental.after.color_histogram"
    ENVIRONMENTAL_AFTER_ASSESSMENT = "environmental.after.assessment"
    ENVIRONMENTAL_SAVINGS = "environmental.savings"
    TRANSFORMATION_HEURISTICS = "transformation.heuristics"
    TRANSFORMATION_OUTPUT_HTML_PATH = "transformation.output.html.path"
    RECOMMENDATIONS = "recommendations"
    RESULTS = "results"


ContextKeyLike = str | ContextKey
