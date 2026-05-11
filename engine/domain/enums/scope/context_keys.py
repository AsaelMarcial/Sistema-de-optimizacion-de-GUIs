from __future__ import annotations

from enum import StrEnum


class ContextRoot(StrEnum):
    SESSION = "session"
    PAGE_BUILDER = "page_builder"
    PROTOTYPE_STRUCTURE = "prototype_structure"
    COLOR = "color"
    SCHEME = "scheme"
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
    PROTOTYPE_STRUCTURE = "prototype_structure"
    COLOR_CATALOG = "color.catalog"
    SCHEME_COLOR_HISTOGRAM = "scheme.color_histogram"
    SCHEME_TONAL_PALETTES = "scheme.tonal_palettes"
    SCHEME_NAMED_COLOR_BREAKDOWN = "scheme.named_color_breakdown"
    STYLE_CATALOG = "style.catalog"
    TOKEN_INVENTORY = "token.inventory"
    DERIVED_RAW_CSS_OVERVIEW = "derived.raw_css_overview"
    DERIVED_RAW_SNAPSHOT_METADATA = "derived.raw_snapshot_metadata"
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
