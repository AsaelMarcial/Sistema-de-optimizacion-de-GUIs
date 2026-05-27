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

    def get_declaration(self, declaration_id: str) -> Declaration | None:
        normalized_declaration_id = _clean_text(declaration_id)
        for declaration in self.declarations:
            if declaration.declaration_id == normalized_declaration_id:
                return declaration
        return None

    def get_declarations(self, property_name: str | None = None) -> tuple[Declaration, ...]:
        if property_name is None:
            return tuple(self.declarations)
        normalized_property = _normalize_property_name(property_name)
        return tuple(
            declaration
            for declaration in self.declarations
            if declaration.property_name == normalized_property
        )

    def is_grouped(self) -> bool:
        return len(self.selectors) > 1

    def is_root_rule(self) -> bool:
        return any(selector.text == ":root" for selector in self.selectors)

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

    def get_rule(self, rule_id: str) -> Rule | None:
        return self._rules_by_id.get(_clean_text(rule_id))

    def get_declaration(
        self,
        declaration_id: str | None = None,
        *,
        rule_id: str | None = None,
        property_name: str | None = None,
    ) -> Declaration | None:
        normalized_declaration_id = _clean_text(declaration_id)
        if normalized_declaration_id:
            for rule in self.rules:
                declaration = rule.get_declaration(normalized_declaration_id)
                if declaration is not None:
                    return declaration
        if rule_id and property_name:
            rule = self.get_rule(_clean_text(rule_id)) # type: ignore
            if rule is None:
                return None
            declarations = rule.get_declarations(property_name)
            return declarations[-1] if declarations else None
        return None

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

    def _source_identity(
        self,
        *,
        kind: StyleSourceKind,
        stylesheet_id: str | None,
        href: str | None,
        owner_node_id: str | None,
    ) -> tuple[StyleSourceKind, str | None, str | None, str | None]:
        return (
            kind,
            _clean_text(stylesheet_id) or None,
            _clean_text(href) or None,
            _clean_text(owner_node_id) or None,
        )

    def _serialize_selector(self, selector: Selector) -> dict[str, object]:
        payload: dict[str, object] = {
            "selector_id": selector.selector_id,
            "text": selector.text,
            "order_in_group": selector.order_in_group,
            "used": selector.used,
        }
        if selector.specificity is not None:
            payload["specificity"] = list(selector.specificity)
        if selector.metadata:
            payload["metadata"] = dict(selector.metadata)
        return payload

    def _serialize_declaration(self, declaration: Declaration) -> dict[str, object]:
        payload: dict[str, object] = {
            "declaration_id": declaration.declaration_id,
            "rule_id": declaration.rule_id,
            "name": str(declaration.property_name),
            "syntax": declaration.kind.value,
            "value_text": declaration.value_text,
            "important": declaration.important,
            "implicit": declaration.implicit,
            "disabled": declaration.disabled,
            "declaration_order": declaration.source_order,
        }
        if declaration.source_range is not None:
            payload["source_range"] = declaration.source_range.to_dict()
        if declaration.covered_longhands:
            payload["covered_longhands"] = list(declaration.covered_longhands)
        if declaration.metadata:
            payload["metadata"] = dict(declaration.metadata)
        return payload

    def _serialize_rule(self, rule: Rule) -> dict[str, object]:
        payload: dict[str, object] = {
            "rule_id": rule.rule_id,
            "source_id": rule.source_id,
            "rule_type": rule.rule_type.value,
            "source_kind": rule.source_kind.value,
            "selector_text": rule.selector_text,
            "selectors": [self._serialize_selector(selector) for selector in rule.selectors],
            "declarations": [self._serialize_declaration(declaration) for declaration in rule.declarations],
            "source_order": rule.source_order,
            "used": rule.used,
            "disabled": rule.disabled,
        }
        if rule.source_range is not None:
            payload["source_range"] = rule.source_range.to_dict()
        if rule.stylesheet_id is not None:
            payload["stylesheet_id"] = rule.stylesheet_id
        if rule.source_url is not None:
            payload["source_url"] = rule.source_url
        if rule.owner_element_id is not None:
            payload["owner_element_id"] = rule.owner_element_id
        if rule.at_rule_contexts:
            payload["at_context"] = [
                {"name": context.name, "prelude": context.prelude}
                for context in rule.at_rule_contexts
            ]
        if rule.metadata:
            payload["metadata"] = dict(rule.metadata)
        return payload

    def _serialize_source(self, source: StyleSource) -> dict[str, object]:
        payload: dict[str, object] = {
            "source_id": source.source_id,
            "source_kind": source.kind.value,
            "source_order": source.source_order,
            "rules": [self._serialize_rule(rule) for rule in source.rules],
            "disabled": source.disabled,
            "alternate": source.alternate,
        }
        if source.stylesheet_id is not None:
            payload["stylesheet_id"] = source.stylesheet_id
        if source.href is not None:
            payload["href"] = source.href
            payload["source_url"] = source.href
        if source.media is not None:
            payload["media"] = source.media
        if source.title is not None:
            payload["title"] = source.title
        if source.owner_node_id is not None:
            payload["owner_node_id"] = source.owner_node_id
            payload["owner_element_id"] = source.owner_node_id
        if source.owner_tag is not None:
            payload["owner_tag"] = source.owner_tag
        if source.metadata:
            payload["metadata"] = dict(source.metadata)
        return payload

    def _register_source(self, source: StyleSource) -> StyleSource:
        if source.source_id in self._sources_by_id:
            raise DuplicateSourceError(f"Duplicated source id: {source.source_id}")
        identity = self._source_identity(
            kind=source.kind,
            stylesheet_id=source.stylesheet_id,
            href=source.href,
            owner_node_id=source.owner_node_id,
        )
        if identity in self._sources_by_identity:
            raise DuplicateSourceError(f"Duplicated source identity: {identity}")
        self._sources.append(source)
        self._sources_by_id[source.source_id] = source
        self._sources_by_identity[identity] = source
        return source

    def add_source(
        self,
        source: StyleSource | None = None,
        *,
        kind: StyleSourceKind | str = StyleSourceKind.UNKNOWN,
        source_order: int | None = None,
        source_id: str | None = None,
        stylesheet_id: str | None = None,
        href: str | None = None,
        media: str | None = None,
        disabled: bool = False,
        title: str | None = None,
        alternate: bool = False,
        owner_node_id: str | None = None,
        owner_tag: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> StyleSource:
        if source is None:
            resolved_kind = _infer_source_kind(
                kind,
                stylesheet_id=stylesheet_id,
                href=href,
                owner_node_id=owner_node_id,
            )
            resolved_source_order = len(self._sources) if source_order is None else int(source_order)
            normalized_stylesheet_id = _clean_text(stylesheet_id) or None
            if resolved_kind == StyleSourceKind.EXTERNAL and normalized_stylesheet_id is None:
                normalized_stylesheet_id = generate_stable_id(
                    "stylesheet",
                    resolved_kind.value,
                    _clean_text(href),
                    resolved_source_order,
                )
            if resolved_kind == StyleSourceKind.EMBEDDED and normalized_stylesheet_id is None:
                normalized_stylesheet_id = generate_stable_id(
                    "stylesheet",
                    resolved_kind.value,
                    resolved_source_order,
                )
            identity = self._source_identity(
                kind=resolved_kind,
                stylesheet_id=normalized_stylesheet_id,
                href=href,
                owner_node_id=owner_node_id,
            )
            existing = self._sources_by_identity.get(identity)
            if existing is not None:
                return existing
            source = StyleSource(
                source_id=_clean_text(source_id) or generate_stable_id(
                    "source",
                    resolved_kind.value,
                    _clean_text(normalized_stylesheet_id),
                    _clean_text(href),
                    _clean_text(owner_node_id),
                    resolved_source_order,
                ),
                kind=resolved_kind,
                source_order=resolved_source_order,
                stylesheet_id=normalized_stylesheet_id,
                href=href,
                media=media,
                disabled=disabled,
                title=title,
                alternate=alternate,
                owner_node_id=owner_node_id,
                owner_tag=owner_tag,
                metadata=metadata,
            )
        return self._register_source(source)

    def get_source(self, source_id: str) -> StyleSource | None:
        return self._sources_by_id.get(_clean_text(source_id))

    def rules_for_source_kind(self, source_kind: StyleSourceKind | str) -> tuple[Rule, ...]:
        normalized_kind = _coerce_source_kind(source_kind)
        return tuple(
            rule
            for source in self.sources
            if source.kind == normalized_kind
            for rule in source.rules
        )

    def get_rule(self, rule_id: str) -> Rule:
        normalized_rule_id = _clean_text(rule_id)
        for source in self.sources:
            rule = source.get_rule(normalized_rule_id)
            if rule is not None:
                return rule
        raise StyleCatalogError(f"Rule not found: {rule_id}")

    def get_declaration(
        self,
        declaration_id: str | None = None,
        *,
        rule_id: str | None = None,
        property_name: str | None = None,
        name: str | None = None,
    ) -> Declaration | None:
        normalized_property_name = property_name or name
        for source in self.sources:
            declaration = source.get_declaration(
                declaration_id,
                rule_id=rule_id,
                property_name=normalized_property_name,
            )
            if declaration is not None:
                return declaration
        return None

    def root_custom_property_declarations(self) -> tuple[Declaration, ...]:
        declarations: list[Declaration] = []
        for rule in self.rules:
            if not rule.is_root_rule():
                continue
            declarations.extend(
                declaration
                for declaration in rule.declarations
                if declaration.is_custom_property
            )
        return tuple(declarations)

    def split_grouped_rule(
        self,
        rule_id: str,
        selector_ids: Iterable[str] | None = None,
    ) -> Rule | tuple[Rule, ...]:
        rule = self.get_rule(rule_id)
        if not rule.is_grouped():
            return rule
        selectors = list(rule.selectors)
        if selector_ids is None:
            clones: list[Rule] = []
            rule.selectors = [selectors[0]]
            rule.selector_text = selectors[0].text
            for selector in selectors[1:]:
                clones.append(self._clone_rule_with_selectors(rule, (selector,)))
            return tuple(clones)

        selected_ids = {_clean_text(item) for item in selector_ids if _clean_text(item)}
        selected = tuple(selector for selector in selectors if selector.selector_id in selected_ids)
        remaining = tuple(selector for selector in selectors if selector.selector_id not in selected_ids)
        if not selected:
            raise StyleCatalogError("No valid selectors were provided for split.")
        if not remaining:
            raise StyleCatalogError("Cannot split all selectors out of the original rule.")
        rule.selectors = list(remaining)
        rule.selector_text = ", ".join(selector.text for selector in remaining)
        return self._clone_rule_with_selectors(rule, selected)

    def _clone_rule_with_selectors(self, source_rule: Rule, selectors: tuple[Selector, ...]) -> Rule:
        clone = source_rule.source.add_rule(
            rule_type=source_rule.rule_type,
            selectors=tuple(
                Selector(
                    selector_id=generate_stable_id("selector", source_rule.rule_id, selector.text, index),
                    text=selector.text,
                    order_in_group=index,
                    specificity=selector.specificity,
                    used=selector.used,
                    metadata=dict(selector.metadata),
                )
                for index, selector in enumerate(selectors)
            ),
            at_rule_contexts=source_rule.at_rule_contexts,
            source_range=source_rule.source_range,
            source_order=len(source_rule.source.rules),
            selector_text=", ".join(selector.text for selector in selectors),
        )
        for declaration in source_rule.declarations:
            clone.add_declaration(
                name=declaration.property_name,
                value_text=declaration.value_text,
                syntax=declaration.kind,
                important=declaration.important,
                implicit=declaration.implicit,
                disabled=declaration.disabled,
                declaration_order=declaration.source_order,
                source_range=declaration.source_range,
                covered_longhands=declaration.covered_longhands,
                metadata=dict(declaration.metadata),
            )
        return clone

    def to_dict(self) -> dict[str, object]:
        return {
            "total_sources": len(self.sources),
            "total_rules": len(self.rules),
            "total_declarations": sum(len(rule.declarations) for rule in self.rules),
            "sources": [self._serialize_source(source) for source in self.sources],
            "external_sources": [self._serialize_source(source) for source in self.external_sources],
            "embedded_sources": [self._serialize_source(source) for source in self.embedded_sources],
            "inline_sources": [self._serialize_source(source) for source in self.inline_sources],
            "rules": [self._serialize_rule(rule) for rule in self.rules],
        }
