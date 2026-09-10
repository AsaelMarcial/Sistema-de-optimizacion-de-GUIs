from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from engine.domain.models.color_scheme import Color

# =============================================================================
# SUMMARY DOMAIN
# =============================================================================
#
# This module contains the domain models used to store analysis,
# diagnostics and optimization results generated throughout the
# GLOW pipeline.
#
# These objects are consumed by reporting stages and by the
# results.html interface.
#
# The Summary class acts as the aggregate root and owns all
# collected result entities.
#
# =============================================================================

# =============================================================================
# ENVIRONMENTAL REVIEW
# =============================================================================

# Represents the environmental impact metrics produced after analyzing
# and transforming the prototype.
#
# These values are displayed in the final report and summarize:
# - estimated energy consumption,
# - estimated carbon footprint,
# - estimated carbon footprint reduction achieved by the optimization.
#
# A Summary can only contain a single EnvironmentalReview.

@dataclass(frozen=True, slots=True)
class EnvironmentalReview:

    before_energy_consumption: float = field(init=True)

    before_carbon_footprint: float = field(init=True)

    after_energy_consumption: float = field(init=True)

    after_carbon_footprint: float = field(init=True)

    carbon_footprint_reduction: float = field(init=True)

# =============================================================================
# OVERVIEW
# =============================================================================


# Represents a named piece of information generated during analysis.
#
# Overview entries are intentionally generic and can store:
# - statistics,
# - histograms,
# - percentages,
# - color distributions,
# - chart data,
# - or any other information required by future stages or reports.
#
# The name acts as the unique identifier within Summary.

@dataclass(frozen=True, slots=True)
class Overview:

    name: str = field(init=True)

    data: Any = field(init=True)


# =============================================================================
# CONTRAST ISSUE
# =============================================================================


# Represents an accessibility issue caused by insufficient contrast
# between a foreground and background color.
#
# Each issue references:
# - the affected DOM node,
# - the measured contrast ratio,
# - the required WCAG ratio,
# - the foreground color,
# - the background color.
#
# These issues are used by reports and recommendation systems.

@dataclass(frozen=True, slots=True)
class ContrastIssue:

    issue_id: int = field(init=True)

    backend_node_id: int = field(init=True)

    contrast_ratio: float = field(init=True)

    required_ratio: float = field(init=True)

    is_large_text: bool = field(init=True)

    foreground: str = field(init=True)

    background: str = field(init=True)

# =============================================================================
# WARNING
# =============================================================================


# Represents a non-fatal problem detected during processing.
#
# Warnings are intended for diagnostics and troubleshooting and
# allow the pipeline to continue running even when some operations
# cannot be completed successfully.
#
# Examples:
# - unsupported CSS values,
# - parsing failures,
# - inaccessible resources,
# - malformed color definitions.

@dataclass(frozen=True, slots=True)
class Warning:

    warning_id: int = field(init=True)

    code: str = field(init=True)

    message: str = field(init=True)

    backend_node_id: int | None = field(default=None)

    node_id: int | None = field(default=None)


# =============================================================================
# SUMMARY
# =============================================================================


# Aggregate root that centralizes all analysis results generated
# throughout the pipeline.
#
# Summary is the primary source of information used by results.html
# and stores:
#
# - environmental metrics,
# - overview statistics,
# - contrast issues,
# - processing warnings.
#
# This class owns the lifecycle of all contained objects and
# guarantees uniqueness through its add_* methods.

class Summary:

    def __init__(self) -> None:

        self.__environmental_review: EnvironmentalReview | None = None

        self.__overviews: dict[str, Overview] = {}

        self.__contrast_issues: dict[int, ContrastIssue] = {}

        self.__warnings: dict[int, Warning] = {}

    # =========================================================================
    # ENVIRONMENTAL REVIEW
    # =========================================================================

    def add_environmental_review(
        self,
        before_energy_consumption: float,
        before_carbon_footprint: float,
        after_energy_consumption: float,
        after_carbon_footprint: float,        
        carbon_footprint_reduction: float,
    ) -> EnvironmentalReview:

        if self.__environmental_review is not None:
            return self.__environmental_review

        review = EnvironmentalReview(
            before_energy_consumption=before_energy_consumption,
            before_carbon_footprint=before_carbon_footprint,
            after_energy_consumption=after_energy_consumption,
            after_carbon_footprint=after_carbon_footprint,
            carbon_footprint_reduction=carbon_footprint_reduction,
        )

        self.__environmental_review = review

        return review

    # =========================================================================
    # OVERVIEW
    # =========================================================================

    def add_overview(
        self,
        name: str,
        data: Any,
    ) -> Overview:

        if not name:
            raise ValueError("Overview name cannot be empty.")

        if name in self.__overviews:
            return self.__overviews[name]

        overview = Overview(
            name=name,
            data=data,
        )

        self.__overviews[name] = overview

        return overview

    # =========================================================================
    # CONTRAST ISSUES
    # =========================================================================

    def add_contrast_issue(
        self,
        issue_id: int,
        backend_node_id: int,
        contrast_ratio: float,
        required_ratio: float,
        is_large_text: bool,
        foreground: Color,
        background: Color,
    ) -> ContrastIssue:

        if issue_id in self.__contrast_issues:
            return self.__contrast_issues[issue_id]

        issue = ContrastIssue(
            issue_id=issue_id,
            backend_node_id=backend_node_id,
            contrast_ratio=contrast_ratio,
            required_ratio=required_ratio,
            is_large_text=is_large_text,
            foreground=foreground,
            background=background,
        )

        self.__contrast_issues[issue_id] = issue

        return issue

    # =========================================================================
    # WARNINGS
    # =========================================================================

    def add_warning(
        self,
        warning_id: int,
        code: str,
        message: str,
        backend_node_id: int | None = None,
        node_id: int | None = None,
    ) -> Warning:

        if warning_id in self.__warnings:
            return self.__warnings[warning_id]

        issue = Warning(
            warning_id=warning_id,
            code=code,
            message=message,
            backend_node_id=backend_node_id,
            node_id=node_id,
        )

        self.__warnings[warning_id] = issue

        return issue

    # =========================================================================
    # GETTERS
    # =========================================================================

    def environmental_review(
        self,
    ) -> EnvironmentalReview | None:

        return self.__environmental_review

    def overviews(
        self,
    ) -> dict[str, Overview]:

        return self.__overviews

    def overview(
        self,
        name: str,
    ) -> Overview | None:

        return self.__overviews.get(name)

    def contrast_issues(
        self,
    ) -> dict[int, ContrastIssue]:

        return self.__contrast_issues

    @property
    def warnings(
        self,
    ) -> tuple[Warning, ...]:

        return tuple(self.__warnings.values())

    # =========================================================================
    # ITERATORS
    # =========================================================================

    def iter_overviews(
        self,
    ) -> Iterator[Overview]:

        yield from self.__overviews.values()

    def iter_contrast_issues(
        self,
    ) -> Iterator[ContrastIssue]:

        yield from self.__contrast_issues.values()

    def iter_warnings(
        self,
    ) -> Iterator[Warning]:

        yield from self.__warnings.values()
