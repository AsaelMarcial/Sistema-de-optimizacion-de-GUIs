from __future__ import annotations

from collections import Counter
from itertools import chain
from dataclasses import dataclass, field
from typing import Any, Literal

from flask import g, has_app_context

from engine.domain.models.project_context import ProjectFile, Resource
from engine.utilities.token_specification import Value, classify_value

StyleSourceType = Literal[
    "rule",
    "inline",
    "attribute",
]
StylesheetKind = Literal[
    "embedded",
    "external",
    "unavailable",
]


@dataclass(slots=True)
class CSSProperty:
    name: str
    value: str
    range: dict[str, int] | tuple[int, int, int, int] | None = None
    classification: tuple[Value, ...] = field(init=False)

    def __post_init__(self) -> None:
        self.name = self.name.strip().lower()
        self.value = str(self.value or "").strip()
        self.classification = classify_value(self.value)


@dataclass(slots=True)
class CSSStyle:
    source: StyleSourceType
    properties: list[CSSProperty] = field(default_factory=list)
    elements: Counter[int] = field(default_factory=Counter)
    range: dict[str, int] | tuple[int, int, int, int] | None = None

    def add_property(self, property_: CSSProperty) -> CSSProperty:
        self.properties.append(property_)
        return property_

    def find_property(self, name: str) -> CSSProperty | None:
        normalized = str(name or "").strip().lower()
        return next(
            (property_ for property_ in self.properties if property_.name == normalized),
            None,
        )

    def iter_properties(self):
        return iter(self.properties)

    def __iter__(self):
        return self.iter_properties()


@dataclass(slots=True)
class CSSRule:
    selectors: Counter[tuple[str, int]] = field(default_factory=Counter)
    properties: list[CSSProperty] = field(default_factory=list)
    range: dict[str, int] | tuple[int, int, int, int] | None = None
    style_range: dict[str, int] | tuple[int, int, int, int] | None = None
    origin: str = "regular"

    def add_selector(self, selector: str, backend_node_id: int) -> None:
        self.selectors[(selector, backend_node_id)] += 1

    def add_property(self, property_: CSSProperty) -> CSSProperty:
        self.properties.append(property_)
        return property_

    def find_property(self, name: str) -> CSSProperty | None:
        normalized = str(name or "").strip().lower()
        return next(
            (property_ for property_ in self.properties if property_.name == normalized),
            None,
        )

    def iter_properties(self):
        return iter(self.properties)

    def __iter__(self):
        return self.iter_properties()


@dataclass(slots=True)
class Stylesheet:
    stylesheet_id: str
    frame_id: str
    source_url: str
    origin: str = ""
    disabled: bool = False
    is_inline: bool = False
    is_mutable: bool = False
    is_constructed: bool = False
    loading_failed: bool = False
    owner_node: int | None = None
    parent_stylesheet_id: str | None = None
    original_text: str = ""
    current_text: str = ""
    changes: int = 0
    rules: list[CSSRule] = field(default_factory=list)
    styles: list[CSSStyle] = field(default_factory=list)

    @property
    def style_sheet_id(self) -> str:
        return self.stylesheet_id

    @property
    def resource_url(self) -> str:
        return self.source_url

    @property
    def resource(self) -> Resource | None:
        if not has_app_context() or getattr(g, "project_context", None) is None:
            return None

        resource = g.project_context.resources.get(self.resource_url)
        if resource is not None:
            return resource

        project_file = g.project_context.project_file(self.resource_url)
        return None if project_file is None else project_file.runtime_information

    @property
    def project_file(self) -> ProjectFile | None:
        resource = self.resource
        return None if resource is None else resource.project_file

    @property
    def kind(self) -> StylesheetKind:
        if (
            not self.frame_id
            or self.disabled
            or self.loading_failed
            or self.is_constructed
        ):
            return "unavailable"

        if self.is_inline:
            return "embedded"

        if self.source_url:
            return "external"

        return "unavailable"

    @property
    def changed(self) -> bool:
        self.changes += 1
        return True

    def add_rule(self, rule: CSSRule) -> CSSRule:
        if found := self.find_rule(rule.range):
            found.selectors.update(rule.selectors)
            return found

        self.rules.append(rule)
        return rule

    def add_style(self, style: CSSStyle) -> CSSStyle:
        if found := self.find_style(style.range, style.source):
            found.elements.update(style.elements)
            return found

        self.styles.append(style)
        return style

    def find_rule(
        self,
        range_: dict[str, int] | tuple[int, int, int, int] | None,
    ) -> CSSRule | None:
        return next((rule for rule in self.rules if rule.range == range_), None)

    def find_style(
        self,
        range_: dict[str, int] | tuple[int, int, int, int] | None,
        source: str | None = None,
    ) -> CSSStyle | None:
        return next(
            (
                style
                for style in self.styles
                if style.range == range_
                and (source is None or style.source == source)
            ),
            None,
        )

    def iter_properties(self):
        return chain.from_iterable(item.iter_properties() for item in self)

    def find_properties(self, name: str) -> tuple[CSSProperty, ...]:
        normalized = str(name or "").strip().lower()
        return tuple(
            property_
            for property_ in self.iter_properties()
            if property_.name == normalized
        )

    def __iter__(self):
        return chain(self.rules, self.styles)

    def __contains__(self, item: object) -> bool:
        match item:
            case CSSRule():
                return self.find_rule(item.range) is not None
            case CSSStyle():
                return self.find_style(item.range, item.source) is not None
            case ProjectFile():
                return item == self.project_file
            case str():
                return item == self.stylesheet_id

        return False


StyleSheet = Stylesheet


@dataclass(slots=True)
class StyleSource:
    target_property: str
    declaration_name: str
    value: str
    source_type: StyleSourceType
    stylesheet_id: str | None = None
    selector: str | None = None
    origin: str = "regular"
    important: bool = False
    disabled: bool = False
    declaration_range: dict[str, int] | None = None
    style_range: dict[str, int] | None = None
    classification: tuple[Value, ...] = field(
        init=False,
        repr=False,
        hash=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        self.target_property = self.target_property.strip().lower()
        self.declaration_name = self.declaration_name.strip().lower()
        self.value = str(self.value or "").strip()
        self.classification = classify_value(self.value)


class Styles:
    def __init__(self) -> None:
        self.stylesheets: dict[str, Stylesheet] = {}
        self.sources_by_node: dict[int, dict[str, list[StyleSource]]] = {}

    def register_stylesheet(self, header: dict[str, Any]) -> Stylesheet | None:
        stylesheet_id = header.get("styleSheetId")

        if not stylesheet_id:
            return None

        stylesheet = Stylesheet(
            stylesheet_id=str(stylesheet_id),
            frame_id=str(header.get("frameId") or ""),
            source_url=str(header.get("sourceURL") or ""),
            origin=str(header.get("origin") or ""),
            disabled=bool(header.get("disabled", False)),
            is_inline=bool(header.get("isInline", False)),
            is_mutable=bool(header.get("isMutable", False)),
            is_constructed=bool(header.get("isConstructed", False)),
            loading_failed=bool(header.get("loadingFailed", False)),
            owner_node=header.get("ownerNode"),
            parent_stylesheet_id=header.get("parentStyleSheetId"),
        )

        self.stylesheets[stylesheet.stylesheet_id] = stylesheet
        return stylesheet

    def set_stylesheet_text(
        self,
        stylesheet_id: str,
        text: str,
        *,
        initialize: bool = False,
    ) -> None:
        stylesheet = self.get_stylesheet(stylesheet_id)

        if stylesheet is None:
            return

        if initialize and not stylesheet.original_text:
            stylesheet.original_text = text

        stylesheet.current_text = text

    def get_stylesheet(self, stylesheet_id: str) -> Stylesheet | None:
        return self.stylesheets.get(stylesheet_id)

    def get_document_stylesheets(self, frame_id: str) -> tuple[Stylesheet, ...]:
        return tuple(
            stylesheet
            for stylesheet in self.stylesheets.values()
            if stylesheet.frame_id == frame_id
        )

    def loaded_css(self) -> tuple[Stylesheet, ...]:
        loaded: list[Stylesheet] = []
        for stylesheet in self.stylesheets.values():
            resource = stylesheet.resource
            project_file = None if resource is None else resource.project_file
            if (
                stylesheet.kind != "unavailable"
                and resource is not None
                and resource.is_loaded
                and project_file is not None
                and project_file.file_type == "css"
                and project_file.path.name != "glow.css"
            ):
                loaded.append(stylesheet)

        return tuple(loaded)

    def iter_properties(self):
        return chain.from_iterable(
            stylesheet.iter_properties()
            for stylesheet in self.stylesheets.values()
        )

    def find_properties(self, name: str) -> tuple[CSSProperty, ...]:
        normalized = str(name or "").strip().lower()
        return tuple(
            property_
            for property_ in self.iter_properties()
            if property_.name == normalized
        )

    def register_element_sources(
        self,
        backend_node_id: int,
        matched_styles: dict[str, Any],
        property_names: set[str],
        *,
        include_user_agent: bool = False,
        include_inspector: bool = False,
    ) -> dict[str, list[StyleSource]]:
        sources = self.extract_property_sources(
            matched_styles=matched_styles,
            property_names=property_names,
            include_user_agent=include_user_agent,
            include_inspector=include_inspector,
        )

        self.sources_by_node[backend_node_id] = sources
        return sources

    def get_sources(
        self,
        backend_node_id: int,
        property_name: str,
    ) -> tuple[StyleSource, ...]:
        return tuple(
            self.sources_by_node.get(backend_node_id, {}).get(property_name, ())
        )

    def clear(self) -> None:
        self.stylesheets.clear()
        self.sources_by_node.clear()

    @staticmethod
    def extract_property_sources(
        matched_styles: dict[str, Any],
        property_names: set[str],
        *,
        include_user_agent: bool = False,
        include_inspector: bool = False,
    ) -> dict[str, list[StyleSource]]:
        sources: dict[str, list[StyleSource]] = {
            property_name: []
            for property_name in property_names
        }
        allowed_origins = {"regular"}

        if include_user_agent:
            allowed_origins.add("user-agent")

        if include_inspector:
            allowed_origins.add("inspector")

        def affected_properties(css_property: dict[str, Any]) -> set[str]:
            affected = {str(css_property.get("name") or "")}
            affected.update(
                str(longhand.get("name") or "")
                for longhand in css_property.get("longhandProperties", ())
            )
            return affected & property_names

        def add_style_properties(
            style: dict[str, Any],
            *,
            source_type: StyleSourceType,
            selector: str | None,
            origin: str,
        ) -> None:
            for css_property in style.get("cssProperties", ()):
                if css_property.get("disabled", False):
                    continue

                if css_property.get("parsedOk") is False:
                    continue

                targets = affected_properties(css_property)
                if not targets:
                    continue

                declaration_name = str(css_property.get("name") or "")
                declaration_value = str(css_property.get("value") or "")

                for target_property in targets:
                    sources[target_property].append(
                        StyleSource(
                            target_property=target_property,
                            declaration_name=declaration_name,
                            value=declaration_value,
                            source_type=source_type,
                            stylesheet_id=style.get("styleSheetId"),
                            selector=selector,
                            origin=origin,
                            important=bool(css_property.get("important", False)),
                            disabled=False,
                            declaration_range=css_property.get("range"),
                            style_range=style.get("range"),
                        )
                    )

        inline_style = matched_styles.get("inlineStyle")
        if inline_style:
            add_style_properties(
                inline_style,
                source_type="inline",
                selector=None,
                origin="regular",
            )

        attributes_style = matched_styles.get("attributesStyle")
        if attributes_style:
            add_style_properties(
                attributes_style,
                source_type="attribute",
                selector=None,
                origin="regular",
            )

        for matched_rule in matched_styles.get("matchedCSSRules", ()):
            rule = matched_rule.get("rule") or {}
            origin = str(rule.get("origin") or "")

            if origin not in allowed_origins:
                continue

            style = rule.get("style") or {}
            selector_list = rule.get("selectorList") or {}
            selectors = selector_list.get("selectors", ())
            matching_indexes = matched_rule.get("matchingSelectors", ())
            matched_selector_texts = [
                str(selectors[index].get("text") or "")
                for index in matching_indexes
                if 0 <= index < len(selectors)
            ]
            selector = ", ".join(text for text in matched_selector_texts if text)

            if not selector:
                selector = str(selector_list.get("text") or "")

            add_style_properties(
                style,
                source_type="rule",
                selector=selector,
                origin=origin,
            )

        return {
            property_name: property_sources
            for property_name, property_sources in sources.items()
            if property_sources
        }


StyleCatalog = Styles
