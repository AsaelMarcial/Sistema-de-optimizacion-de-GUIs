from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from hashlib import sha1

from engine.domain.enums.types.style import DeclarationSyntax, RuleType, StyleSourceKind


class StyleCatalogError(Exception):
    """Base style catalog exception."""


_SUPPLEMENTAL_SHORTHANDS: dict[str, tuple[str, ...]] = {
    "margin": ("margin-top", "margin-right", "margin-bottom", "margin-left"),
    "padding": ("padding-top", "padding-right", "padding-bottom", "padding-left"),
    "border": (
        "border-top",
        "border-right",
        "border-bottom",
        "border-left",
        "border-width",
        "border-style",
        "border-color",
    ),
    "border-top": ("border-top-width", "border-top-style", "border-top-color"),
    "border-right": ("border-right-width", "border-right-style", "border-right-color"),
    "border-bottom": ("border-bottom-width", "border-bottom-style", "border-bottom-color"),
    "border-left": ("border-left-width", "border-left-style", "border-left-color"),
    "border-width": ("border-top-width", "border-right-width", "border-bottom-width", "border-left-width"),
    "border-style": ("border-top-style", "border-right-style", "border-bottom-style", "border-left-style"),
    "border-color": ("border-top-color", "border-right-color", "border-bottom-color", "border-left-color"),
    "outline": ("outline-width", "outline-style", "outline-color"),
    "background": (
        "background-color",
        "background-image",
        "background-repeat",
        "background-position",
        "background-size",
        "background-attachment",
        "background-clip",
        "background-origin",
    ),
    "text-decoration": (
        "text-decoration-line",
        "text-decoration-style",
        "text-decoration-color",
        "text-decoration-thickness",
    ),
    "text-emphasis": ("text-emphasis-color",),
    "column-rule": ("column-rule-width", "column-rule-style", "column-rule-color"),
    "font": (
        "font-style",
        "font-variant",
        "font-weight",
        "font-stretch",
        "font-size",
        "line-height",
        "font-family",
    ),
}


def generate_stable_id(*parts: object) -> str:
    raw = "::".join(str(part) for part in parts)
    return sha1(raw.encode("utf-8")).hexdigest()


def _clean_text(value: object | None) -> str:
    return str(value or "").strip()


def _normalize_property_name(value: object | None) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    if text.startswith("--"):
        return text
    return text.lower()


def _coerce_scope_property(value: object | None) -> str:
    return _normalize_property_name(value)


def _coerce_rule_type(value: RuleType | str | None) -> RuleType:
    if isinstance(value, RuleType):
        return value
    return RuleType(_clean_text(value) or RuleType.STYLE.value)


def _coerce_source_kind(value: StyleSourceKind | str | None) -> StyleSourceKind:
    if isinstance(value, StyleSourceKind):
        return value
    return StyleSourceKind(_clean_text(value).lower() or StyleSourceKind.UNKNOWN.value)


def _coerce_declaration_syntax(
    *,
    property_name: str,
    kind: DeclarationSyntax | str | None,
    covered_longhands: tuple[str, ...],
) -> DeclarationSyntax:
    normalized_property = _normalize_property_name(property_name)
    if normalized_property.startswith("--"):
        return DeclarationSyntax.CUSTOM_PROPERTY
    if isinstance(kind, DeclarationSyntax):
        return kind
    if kind is not None:
        return DeclarationSyntax(_clean_text(kind))
    return DeclarationSyntax.SHORTHAND if covered_longhands else DeclarationSyntax.LONGHAND


def _coerce_source_range(value: SourceRange | Mapping[str, object] | None) -> SourceRange | None:
    if value is None or isinstance(value, SourceRange):
        return value
    return SourceRange(
        start_line=int(value["start_line"]),  # type: ignore
        start_column=int(value["start_column"]),  # type: ignore
        end_line=int(value["end_line"]),  # type: ignore
        end_column=int(value["end_column"]),  # type: ignore
    )


def _infer_source_kind(
    value: StyleSourceKind | str | None,
    *,
    stylesheet_id: str | None,
    href: str | None,
    owner_node_id: str | None,
) -> StyleSourceKind:
    source_kind = _coerce_source_kind(value)
    if source_kind != StyleSourceKind.UNKNOWN:
        return source_kind
    if _clean_text(owner_node_id):
        return StyleSourceKind.INLINE
    if _clean_text(href):
        return StyleSourceKind.EXTERNAL
    if _clean_text(stylesheet_id):
        return StyleSourceKind.EMBEDDED
    return StyleSourceKind.EMBEDDED


def _shorthand_targets(property_name: str) -> tuple[str, ...]:
    normalized_name = _normalize_property_name(property_name)
    ordered: list[str] = []
    seen: set[str] = set()
    for item in _SUPPLEMENTAL_SHORTHANDS.get(normalized_name, ()):
        normalized_item = _normalize_property_name(item)
        if normalized_item and normalized_item not in seen:
            seen.add(normalized_item)
            ordered.append(normalized_item)
    return tuple(ordered)


def _resolve_covered_longhands(property_name: str, covered_longhands: tuple[str, ...]) -> tuple[str, ...]:
    normalized_property = _normalize_property_name(property_name)
    seeds = tuple(_normalize_property_name(item) for item in covered_longhands if _clean_text(item)) or _shorthand_targets(normalized_property)
    ordered: list[str] = []
    seen: set[str] = set()

    def _visit(candidate: str) -> None:
        normalized_candidate = _normalize_property_name(candidate)
        if (
            not normalized_candidate
            or normalized_candidate == normalized_property
            or normalized_candidate in seen
        ):
            return
        seen.add(normalized_candidate)
        ordered.append(normalized_candidate)
        for nested in _shorthand_targets(normalized_candidate):
            _visit(nested)

    for seed in seeds:
        _visit(seed)
    return tuple(ordered)


def _rule_sort_key(rule: Rule) -> tuple[int, str]:
    return (
        int(rule.source_order),
        rule.rule_id,
    )


@dataclass(slots=True, frozen=True)
class SourceRange:
    start_line: int
    start_column: int
    end_line: int
    end_column: int

    def __post_init__(self) -> None:
        if self.start_line < 1:
            raise ValueError("start_line must be >= 1.")
        if self.end_line < self.start_line:
            raise ValueError("end_line cannot be before start_line.")
        if self.start_column < 0 or self.end_column < 0:
            raise ValueError("columns cannot be negative.")
        if self.end_line == self.start_line and self.end_column < self.start_column:
            raise ValueError("end_column cannot be before start_column.")

    @property
    def key(self) -> tuple[int, int, int, int]:
        return (
            self.start_line,
            self.start_column,
            self.end_line,
            self.end_column,
        )

    @property
    def compact_key(self) -> str:
        return f"l{self.start_line}c{self.start_column}-l{self.end_line}c{self.end_column}"

    def to_dict(self) -> dict[str, int]:
        return {
            "start_line": self.start_line,
            "start_column": self.start_column,
            "end_line": self.end_line,
            "end_column": self.end_column,
        }


@dataclass(slots=True, frozen=True)
class AtRuleContext:
    name: str
    prelude: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _clean_text(self.name))
        object.__setattr__(self, "prelude", _clean_text(self.prelude))

    @property
    def signature_key(self) -> tuple[str, str]:
        return (self.name, self.prelude)


@dataclass(slots=True)
class Selector:
    selector_id: str
    text: str
    order_in_group: int
    specificity: tuple[int, int, int] | None = None
    used: bool = False
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.selector_id = _clean_text(self.selector_id)
        self.text = _clean_text(self.text)
        if not self.selector_id:
            raise ValueError("selector_id is required.")
        if not self.text:
            raise ValueError("selector text is required.")
        if self.order_in_group < 0:
            raise ValueError("order_in_group cannot be negative.")
        if self.specificity is not None and len(self.specificity) != 3:
            raise ValueError("specificity must be a 3-item tuple.")
        self.metadata = dict(self.metadata or {})

    @property
    def source_order(self) -> int:
        return self.order_in_group

    def mark_used(self) -> None:
        self.used = True

    def clear_used(self) -> None:
        self.used = False

@dataclass(slots=True)
class Declaration:
    declaration_id: str
    rule_id: str
    property_name: str
    value_text: str
    source_order: int
    kind: DeclarationSyntax
    important: bool = False
    implicit: bool = False
    disabled: bool = False
    source_range: SourceRange | None = None
    covered_longhands: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.declaration_id = _clean_text(self.declaration_id)
        self.rule_id = _clean_text(self.rule_id)
        self.property_name = _coerce_scope_property(self.property_name)
        self.value_text = _clean_text(self.value_text)
        if not self.declaration_id:
            raise ValueError("declaration_id is required.")
        if not self.rule_id:
            raise ValueError("rule_id is required.")
        if not self.property_name:
            raise ValueError("property_name is required.")
        if self.source_order < 0:
            raise ValueError("source_order cannot be negative.")
        self.covered_longhands = _resolve_covered_longhands(
            str(self.property_name),
            tuple(self.covered_longhands),
        )
        self.kind = _coerce_declaration_syntax(
            property_name=str(self.property_name),
            kind=self.kind,
            covered_longhands=self.covered_longhands,
        )
        self.metadata = dict(self.metadata or {})

    @property
    def name(self) -> str:
        return self.property_name

    @property
    def syntax(self) -> DeclarationSyntax:
        return self.kind

    @property
    def declaration_order(self) -> int:
        return self.source_order

    @property
    def is_custom_property(self) -> bool:
        return self.kind == DeclarationSyntax.CUSTOM_PROPERTY

    @property
    def is_shorthand(self) -> bool:
        return self.kind == DeclarationSyntax.SHORTHAND

    @property
    def is_longhand(self) -> bool:
        return self.kind == DeclarationSyntax.LONGHAND

    @property
    def is_variable(self) -> bool:
        return str(self.property_name).startswith("--")

    def covers_property(self, property_name: str) -> bool:
        normalized_property = _normalize_property_name(property_name)
        return normalized_property == str(self.property_name) or normalized_property in self.covered_longhands


class DuplicateSourceError(StyleCatalogError):
    """Raised when a duplicated source is added."""


class DuplicateRuleError(StyleCatalogError):
    """Raised when a duplicated rule is added."""


class DuplicateSelectorError(StyleCatalogError):
    """Raised when a duplicated selector is added."""


class DuplicateDeclarationError(StyleCatalogError):
    """Raised when a duplicated declaration is added."""


class Rule:
    __slots__ = (
        "rule_id",
        "source_id",
        "selector_text",
        "source_order",
        "source_range",
        "disabled",
        "rule_type",
        "selectors",
        "declarations",
        "at_rule_contexts",
        "metadata",
        "_source",
    )

    def __init__(
        self,
        *,
        rule_id: str,
        source_id: str,
        selector_text: str,
        source_order: int,
        rule_type: RuleType | str = RuleType.STYLE,
        selectors: Iterable[Selector] | None = None,
        declarations: Iterable[Declaration] | None = None,
        at_rule_contexts: Iterable[AtRuleContext] | None = None,
        source_range: SourceRange | None = None,
        disabled: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.rule_id = _clean_text(rule_id)
        self.source_id = _clean_text(source_id)
        self.selector_text = _clean_text(selector_text)
        self.source_order = int(source_order)
        self.source_range = source_range
        self.disabled = bool(disabled)
        self.rule_type = _coerce_rule_type(rule_type)
        self.selectors: list[Selector] = []
        self.declarations: list[Declaration] = []
        self.at_rule_contexts = tuple(at_rule_contexts or ())
        self.metadata = dict(metadata or {})
        self._source: StyleSource | None = None

        if not self.rule_id:
            raise ValueError("rule_id is required.")
        if not self.source_id:
            raise ValueError("source_id is required.")
        if self.source_order < 0:
            raise ValueError("source_order cannot be negative.")

        for selector in selectors or ():
            self.add_selector(selector)
        for declaration in declarations or ():
            self.add_declaration(declaration)
        if not self.selector_text and self.selectors:
            self.selector_text = ", ".join(selector.text for selector in self.selectors)

    @property
    def source_kind(self) -> StyleSourceKind:
        return self._source.kind if self._source is not None else StyleSourceKind.UNKNOWN

    @property
    def stylesheet_id(self) -> str | None:
        return self._source.stylesheet_id if self._source is not None else None

    @property
    def source_url(self) -> str | None:
        return self._source.href if self._source is not None else None

    @property
    def owner_element_id(self) -> str | None:
        return self._source.owner_node_id if self._source is not None else None

    @property
    def used(self) -> bool:
        return any(selector.used for selector in self.selectors)

    @property
    def source(self) -> StyleSource:
        if self._source is None:
            raise StyleCatalogError(f"Rule {self.rule_id} is not attached to a style source.")
        return self._source

    def _attach_source(self, source: StyleSource) -> None:
        self._source = source

    def add_selector(
        self,
        selector: Selector | None = None,
        *,
        text: str | None = None,
        selector_id: str | None = None,
        order_in_group: int | None = None,
        used: bool = False,
        specificity: tuple[int, int, int] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> Selector:
        if selector is None:
            normalized_text = _clean_text(text)
            resolved_order = len(self.selectors) if order_in_group is None else int(order_in_group)
            selector = Selector(
                selector_id=_clean_text(selector_id) or generate_stable_id("selector", self.rule_id, normalized_text, resolved_order),
                text=normalized_text,
                order_in_group=resolved_order,
                specificity=specificity,
                used=used,
                metadata=metadata or {},
            )
        for existing in self.selectors:
            if existing.selector_id == selector.selector_id:
                raise DuplicateSelectorError(f"Duplicated selector id: {selector.selector_id}")
            if existing.text == selector.text:
                raise DuplicateSelectorError(f"Duplicated selector text: {selector.text}")
            if existing.order_in_group == selector.order_in_group:
                raise DuplicateSelectorError(
                    f"Duplicated selector order in rule {self.rule_id}: {selector.order_in_group}"
                )
        self.selectors.append(selector)
        self.selectors.sort(key=lambda item: (item.source_order, item.selector_id))
        self.selector_text = ", ".join(item.text for item in self.selectors)
        return selector

    def get_selector(self, selector_id: str) -> Selector | None:
        normalized_selector_id = _clean_text(selector_id)
        for selector in self.selectors:
            if selector.selector_id == normalized_selector_id:
                return selector
        return None

    def add_declaration(
        self,
        declaration: Declaration | None = None,
        *,
        declaration_id: str | None = None,
        name: str | None = None,
        value_text: str = "",
        syntax: DeclarationSyntax | str | None = None,
        important: bool = False,
        implicit: bool = False,
        disabled: bool = False,
        declaration_order: int | None = None,
        source_range: SourceRange | Mapping[str, object] | None = None,
        covered_longhands: tuple[str, ...] = (),
        metadata: dict[str, object] | None = None,
    ) -> Declaration:
        if declaration is None:
            property_name = _normalize_property_name(name)
            resolved_order = len(self.declarations) if declaration_order is None else int(declaration_order)
            normalized_range = _coerce_source_range(source_range)
            normalized_longhands = _resolve_covered_longhands(property_name, covered_longhands)
            declaration = Declaration(
                declaration_id=_clean_text(declaration_id) or generate_stable_id("declaration", self.rule_id, property_name, resolved_order),
                rule_id=self.rule_id,
                property_name=property_name,
                value_text=value_text,
                source_order=resolved_order,
                kind=_coerce_declaration_syntax(
                    property_name=property_name,
                    kind=syntax,
                    covered_longhands=normalized_longhands,
                ),
                important=important,
                implicit=implicit,
                disabled=disabled,
                source_range=normalized_range,
                covered_longhands=normalized_longhands,
                metadata=metadata or {},
            )
        identity = (declaration.property_name, declaration.source_order)
        for existing in self.declarations:
            if existing.declaration_id == declaration.declaration_id:
                raise DuplicateDeclarationError(f"Duplicated declaration id: {declaration.declaration_id}")
            if (existing.property_name, existing.source_order) == identity:
                raise DuplicateDeclarationError(f"Duplicated declaration identity: {identity}")
        self.declarations.append(declaration)
        self.declarations.sort(key=lambda item: (item.source_order, item.declaration_id))
        return declaration

class StyleSource:
    __slots__ = (
        "source_id",
        "kind",
        "stylesheet_id",
        "href",
        "media",
        "disabled",
        "title",
        "alternate",
        "owner_node_id",
        "owner_tag",
        "source_order",
        "rules",
        "metadata",
        "_rules_by_id",
        "_rules_by_identity",
    )

    def __init__(
        self,
        *,
        source_id: str,
        kind: StyleSourceKind,
        source_order: int,
        stylesheet_id: str | None = None,
        href: str | None = None,
        media: str | None = None,
        disabled: bool = False,
        title: str | None = None,
        alternate: bool = False,
        owner_node_id: str | None = None,
        owner_tag: str | None = None,
        rules: Iterable[Rule] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:
        self.source_id = _clean_text(source_id)
        self.kind = _coerce_source_kind(kind)
        self.stylesheet_id = _clean_text(stylesheet_id) or None
        self.href = _clean_text(href) or None
        self.media = _clean_text(media) or None
        self.disabled = bool(disabled)
        self.title = _clean_text(title) or None
        self.alternate = bool(alternate)
        self.owner_node_id = _clean_text(owner_node_id) or None
        self.owner_tag = _clean_text(owner_tag) or None
        self.source_order = int(source_order)
        self.rules: list[Rule] = []
        self.metadata = dict(metadata or {})
        self._rules_by_id: dict[str, Rule] = {}
        self._rules_by_identity: dict[tuple[str, int], Rule] = {}

        if not self.source_id:
            raise ValueError("source_id is required.")
        if self.source_order < 0:
            raise ValueError("source_order cannot be negative.")

        for rule in rules or ():
            self.add_rule(rule)

    def add_rule(
        self,
        rule: Rule | None = None,
        *,
        rule_id: str | None = None,
        selector_text: str | None = None,
        source_order: int | None = None,
        rule_type: RuleType | str = RuleType.STYLE,
        selectors: Iterable[Selector | str] = (),
        declarations: Iterable[Declaration] | None = None,
        at_rule_contexts: Iterable[AtRuleContext] | None = None,
        source_range: SourceRange | Mapping[str, object] | None = None,
        disabled: bool = False,
        metadata: dict[str, object] | None = None,
    ) -> Rule:
        if rule is None:
            selector_items = tuple(selectors)
            resolved_source_order = (
                self.source_order
                if source_order is None and not self.rules
                else (
                    max(existing_rule.source_order for existing_rule in self.rules) + 1
                    if source_order is None
                    else int(source_order)
                )
            )
            persisted_selector_text = _clean_text(selector_text)
            if not persisted_selector_text and selector_items:
                persisted_selector_text = ", ".join(
                    item.text if isinstance(item, Selector) else _clean_text(item)
                    for item in selector_items
                    if (item.text if isinstance(item, Selector) else _clean_text(item))
                )
            rule = Rule(
                rule_id=_clean_text(rule_id) or generate_stable_id("rule", self.source_id, persisted_selector_text, resolved_source_order),
                source_id=self.source_id,
                selector_text=persisted_selector_text,
                source_order=resolved_source_order,
                rule_type=rule_type,
                declarations=declarations,
                at_rule_contexts=at_rule_contexts,
                source_range=_coerce_source_range(source_range),
                disabled=disabled,
                metadata=metadata,
            )
            for index, selector in enumerate(selector_items):
                if isinstance(selector, Selector):
                    rule.add_selector(selector)
                else:
                    rule.add_selector(text=str(selector), order_in_group=index)
        if rule.rule_id in self._rules_by_id:
            raise DuplicateRuleError(f"Duplicated rule id: {rule.rule_id}")
        identity = (rule.selector_text, rule.source_order)
        if identity in self._rules_by_identity:
            raise DuplicateRuleError(f"Duplicated rule identity: {identity}")
        if rule.source_id != self.source_id:
            raise DuplicateRuleError(f"Rule {rule.rule_id} does not belong to source {self.source_id}")
        if self.kind != StyleSourceKind.INLINE and rule.owner_element_id is not None:
            raise DuplicateRuleError(f"Only inline sources may own element-scoped rules: {rule.rule_id}")
        self.rules.append(rule)
        self.rules.sort(key=_rule_sort_key)
        self._rules_by_id[rule.rule_id] = rule
        self._rules_by_identity[identity] = rule
        rule._attach_source(self)
        return rule

class StyleCatalog:
    __slots__ = ("_sources", "_sources_by_id", "_sources_by_identity")

    def __init__(self) -> None:
        self._sources: list[StyleSource] = []
        self._sources_by_id: dict[str, StyleSource] = {}
        self._sources_by_identity: dict[tuple[StyleSourceKind, str | None, str | None, str | None], StyleSource] = {}

    def __len__(self) -> int:
        return len(self.rules)

    def __iter__(self) -> Iterator[Rule]:
        return iter(self.rules)

    @property
    def sources(self) -> tuple[StyleSource, ...]:
        return tuple(sorted(self._sources, key=lambda source: (source.source_order, source.source_id)))

    @property
    def external_sources(self) -> tuple[StyleSource, ...]:
        return tuple(source for source in self.sources if source.kind == StyleSourceKind.EXTERNAL)

    @property
    def embedded_sources(self) -> tuple[StyleSource, ...]:
        return tuple(source for source in self.sources if source.kind == StyleSourceKind.EMBEDDED)

    @property
    def inline_sources(self) -> tuple[StyleSource, ...]:
        return tuple(source for source in self.sources if source.kind == StyleSourceKind.INLINE)

    @property
    def inline_rules(self) -> tuple[Rule, ...]:
        return tuple(rule for source in self.inline_sources for rule in source.rules)

    @property
    def stylesheets(self) -> tuple[StyleSource, ...]:
        return tuple(
            sorted(
                (*self.embedded_sources, *self.external_sources),
                key=lambda source: (source.source_order, source.source_id),
            )
        )

    @property
    def rules(self) -> tuple[Rule, ...]:
        rules = [rule for source in self.sources for rule in source.rules]
        return tuple(sorted(rules, key=_rule_sort_key))