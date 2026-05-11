from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping

from engine.domain.enums.types.style import DeclarationSyntax, RuleType, StyleSourceKind


class StyleCatalogError(Exception):
    """Raised when the authored style catalog is used incorrectly."""


def _clean_text(value: object | None) -> str:
    return str(value or "").strip()


def _normalize_property_name(value: object | None) -> str:
    text = _clean_text(value)
    if text.startswith("--"):
        return text
    return text.lower()


def _coerce_rule_type(value: RuleType | str | None) -> RuleType:
    if isinstance(value, RuleType):
        return value
    if value is None:
        return RuleType.STYLE
    return RuleType(str(value))


def _coerce_source_kind(value: StyleSourceKind | str | None) -> StyleSourceKind:
    if isinstance(value, StyleSourceKind):
        return value
    if value is None:
        return StyleSourceKind.UNKNOWN
    normalized = _clean_text(value).lower()
    if not normalized:
        return StyleSourceKind.UNKNOWN
    return StyleSourceKind(normalized)


def _coerce_declaration_syntax(
    *,
    name: str,
    syntax: DeclarationSyntax | str | None,
    covered_longhands: tuple[str, ...],
) -> DeclarationSyntax:
    normalized_name = _normalize_property_name(name)
    if normalized_name.startswith("--"):
        return DeclarationSyntax.CUSTOM_PROPERTY
    if syntax is None:
        return DeclarationSyntax.SHORTHAND if covered_longhands else DeclarationSyntax.LONGHAND
    if isinstance(syntax, DeclarationSyntax):
        return syntax
    return DeclarationSyntax(str(syntax))


def _coerce_source_range(value: SourceRange | Mapping[str, object] | None) -> SourceRange | None:
    if value is None or isinstance(value, SourceRange):
        return value
    return SourceRange(
        start_line=int(value["start_line"]),
        start_column=int(value["start_column"]),
        end_line=int(value["end_line"]),
        end_column=int(value["end_column"]),
        start_offset=int(value["start_offset"]) if value.get("start_offset") is not None else None,
        end_offset=int(value["end_offset"]) if value.get("end_offset") is not None else None,
    )


@dataclass(frozen=True, slots=True)
class SourceRange:
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    start_offset: int | None = None
    end_offset: int | None = None

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
    def key(self) -> tuple[int, int, int | None, int, int, int | None]:
        return (
            self.start_line,
            self.start_column,
            self.start_offset,
            self.end_line,
            self.end_column,
            self.end_offset,
        )

    @property
    def compact_key(self) -> str:
        return f"l{self.start_line}c{self.start_column}-l{self.end_line}c{self.end_column}"

    def to_dict(self) -> dict[str, int | None]:
        return {
            "start_line": self.start_line,
            "start_column": self.start_column,
            "start_offset": self.start_offset,
            "end_line": self.end_line,
            "end_column": self.end_column,
            "end_offset": self.end_offset,
        }


@dataclass(frozen=True, slots=True)
class AtRuleContext:
    rule_type: RuleType
    text: str
    source_range: SourceRange | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_type", _coerce_rule_type(self.rule_type))
        object.__setattr__(self, "text", _clean_text(self.text))

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "rule_type": self.rule_type.value,
            "text": self.text,
        }
        if self.source_range is not None:
            payload["source_range"] = self.source_range.to_dict()
        return payload

    @property
    def signature_key(self) -> tuple[str, str, tuple[int, int, int | None, int, int, int | None] | None]:
        return (
            self.rule_type.value,
            self.text,
            self.source_range.key if self.source_range is not None else None,
        )


@dataclass(slots=True)
class Selector:
    selector_id: str
    text: str
    order_in_group: int
    used: bool = False
    specificity: tuple[int, int, int] | None = None

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

    def mark_used(self) -> None:
        self.used = True

    def clear_used(self) -> None:
        self.used = False

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "selector_id": self.selector_id,
            "text": self.text,
            "order_in_group": self.order_in_group,
            "used": self.used,
        }
        if self.specificity is not None:
            payload["specificity"] = list(self.specificity)
        return payload


class Declaration:
    __slots__ = (
        "_declaration_id",
        "_rule_id",
        "_name",
        "_syntax",
        "_value_text",
        "_important",
        "_declaration_order",
        "_source_range",
        "_covered_longhands",
    )

    def __init__(
        self,
        *,
        declaration_id: str,
        rule_id: str,
        name: str,
        value_text: str,
        syntax: DeclarationSyntax | str | None,
        important: bool,
        declaration_order: int,
        source_range: SourceRange | None,
        covered_longhands: tuple[str, ...],
    ) -> None:
        if not declaration_id:
            raise ValueError("declaration_id is required.")
        if not rule_id:
            raise ValueError("rule_id is required.")
        normalized_name = _normalize_property_name(name)
        if not normalized_name:
            raise ValueError("Declaration name is required.")
        if declaration_order < 0:
            raise ValueError("declaration_order cannot be negative.")

        normalized_longhands = tuple(
            _normalize_property_name(item)
            for item in covered_longhands
            if _clean_text(item)
        )
        self._declaration_id = declaration_id
        self._rule_id = rule_id
        self._name = normalized_name
        self._syntax = _coerce_declaration_syntax(
            name=normalized_name,
            syntax=syntax,
            covered_longhands=normalized_longhands,
        )
        self._value_text = _clean_text(value_text)
        self._important = bool(important)
        self._declaration_order = declaration_order
        self._source_range = source_range
        self._covered_longhands = normalized_longhands

    @property
    def declaration_id(self) -> str:
        return self._declaration_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def syntax(self) -> DeclarationSyntax:
        return self._syntax

    @property
    def value_text(self) -> str:
        return self._value_text

    @property
    def important(self) -> bool:
        return self._important

    @property
    def declaration_order(self) -> int:
        return self._declaration_order

    @property
    def source_range(self) -> SourceRange | None:
        return self._source_range

    @property
    def covered_longhands(self) -> tuple[str, ...]:
        return self._covered_longhands

    @property
    def is_variable(self) -> bool:
        return self._name.startswith("--")

    def covers_property(self, property_name: str) -> bool:
        normalized = _normalize_property_name(property_name)
        return normalized == self._name or normalized in self._covered_longhands

    def set_value_text(self, value_text: str) -> None:
        self._value_text = _clean_text(value_text)

    def set_important(self, important: bool) -> None:
        self._important = bool(important)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "declaration_id": self.declaration_id,
            "rule_id": self.rule_id,
            "name": self.name,
            "syntax": self.syntax.value,
            "value_text": self.value_text,
            "important": self.important,
            "declaration_order": self.declaration_order,
        }
        if self.source_range is not None:
            payload["source_range"] = self.source_range.to_dict()
        if self.covered_longhands:
            payload["covered_longhands"] = list(self.covered_longhands)
        return payload


class Rule:
    __slots__ = (
        "_rule_id",
        "_rule_type",
        "_source_kind",
        "_selectors",
        "_selectors_by_id",
        "_selector_texts",
        "_selector_orders",
        "_at_context",
        "_source_range",
        "_source_order",
        "_source_url",
        "_owner_element_id",
        "_declarations_by_id",
        "_declaration_ids_in_order",
        "_declaration_ids_by_name",
        "_declaration_orders",
        "_declaration_signatures",
        "_next_selector_number",
        "_next_declaration_number",
    )

    def __init__(
        self,
        *,
        rule_id: str,
        rule_type: RuleType | str,
        source_kind: StyleSourceKind | str,
        at_context: tuple[AtRuleContext, ...] = (),
        source_range: SourceRange | None = None,
        source_order: int | None = None,
        source_url: str | None = None,
        owner_element_id: str | None = None,
    ) -> None:
        if not rule_id:
            raise ValueError("rule_id is required.")
        self._rule_id = rule_id
        self._rule_type = _coerce_rule_type(rule_type)
        self._source_kind = _coerce_source_kind(source_kind)
        self._selectors: list[Selector] = []
        self._selectors_by_id: dict[str, Selector] = {}
        self._selector_texts: set[str] = set()
        self._selector_orders: set[int] = set()
        self._at_context = tuple(at_context)
        self._source_range = source_range
        self._source_order = source_order
        self._source_url = _clean_text(source_url) or None
        self._owner_element_id = _clean_text(owner_element_id) or None
        self._declarations_by_id: dict[str, Declaration] = {}
        self._declaration_ids_in_order: list[str] = []
        self._declaration_ids_by_name: dict[str, list[str]] = defaultdict(list)
        self._declaration_orders: set[int] = set()
        self._declaration_signatures: set[tuple[str, bool, str, tuple[int, int, int | None, int, int, int | None] | None]] = set()
        self._next_selector_number = 1
        self._next_declaration_number = 1

    def __iter__(self):
        return iter(self.declarations)

    def __len__(self) -> int:
        return len(self._declaration_ids_in_order)

    @property
    def rule_id(self) -> str:
        return self._rule_id

    @property
    def rule_type(self) -> RuleType:
        return self._rule_type

    @property
    def source_kind(self) -> StyleSourceKind:
        return self._source_kind

    @property
    def selectors(self) -> tuple[Selector, ...]:
        return tuple(self._selectors)

    @property
    def selector_text(self) -> str | None:
        if not self._selectors:
            return None
        return ", ".join(selector.text for selector in self._selectors)

    @property
    def at_context(self) -> tuple[AtRuleContext, ...]:
        return self._at_context

    @property
    def source_range(self) -> SourceRange | None:
        return self._source_range

    @property
    def source_order(self) -> int | None:
        return self._source_order

    @property
    def source_url(self) -> str | None:
        return self._source_url

    @property
    def owner_element_id(self) -> str | None:
        return self._owner_element_id

    @property
    def declarations(self) -> tuple[Declaration, ...]:
        return tuple(self._declarations_by_id[item] for item in self._declaration_ids_in_order)

    @property
    def used(self) -> bool:
        return any(selector.used for selector in self._selectors)

    def add_selector(
        self,
        *,
        text: str,
        selector_id: str | None = None,
        order_in_group: int | None = None,
        used: bool = False,
        specificity: tuple[int, int, int] | None = None,
    ) -> Selector:
        normalized_text = _clean_text(text)
        if not normalized_text:
            raise StyleCatalogError("Selector text is required.")
        if selector_id is None:
            selector_id = f"{self.rule_id}:sel-{self._next_selector_number:04d}"
            self._next_selector_number += 1
        selector_id = _clean_text(selector_id)
        if selector_id in self._selectors_by_id:
            raise StyleCatalogError(f"Duplicate selector id: {selector_id}")
        if normalized_text in self._selector_texts:
            raise StyleCatalogError(f"Duplicate selector text in rule {self.rule_id}: {normalized_text}")
        if order_in_group is None:
            order_in_group = len(self._selectors)
        if order_in_group in self._selector_orders:
            raise StyleCatalogError(f"Duplicate selector order in rule {self.rule_id}: {order_in_group}")

        selector = Selector(
            selector_id=selector_id,
            text=normalized_text,
            order_in_group=order_in_group,
            used=used,
            specificity=specificity,
        )
        self._selectors.append(selector)
        self._selectors_by_id[selector.selector_id] = selector
        self._selector_texts.add(selector.text)
        self._selector_orders.add(selector.order_in_group)
        return selector

    def get_selector(self, selector_id: str) -> Selector | None:
        return self._selectors_by_id.get(_clean_text(selector_id))

    def add_declaration(
        self,
        *,
        name: str,
        value_text: str,
        syntax: DeclarationSyntax | str | None = None,
        important: bool = False,
        declaration_order: int | None = None,
        source_range: SourceRange | Mapping[str, object] | None = None,
        covered_longhands: tuple[str, ...] = (),
        declaration_id: str | None = None,
    ) -> Declaration:
        normalized_name = _normalize_property_name(name)
        normalized_value = _clean_text(value_text)
        if declaration_id is None:
            declaration_id = f"{self.rule_id}:decl-{self._next_declaration_number:04d}"
            self._next_declaration_number += 1
        declaration_id = _clean_text(declaration_id)
        if declaration_id in self._declarations_by_id:
            raise StyleCatalogError(f"Duplicate declaration id in rule {self.rule_id}: {declaration_id}")
        if declaration_order is None:
            declaration_order = len(self._declaration_ids_in_order)
        if declaration_order in self._declaration_orders:
            raise StyleCatalogError(f"Duplicate declaration order in rule {self.rule_id}: {declaration_order}")
        normalized_range = _coerce_source_range(source_range)
        signature = (
            normalized_name,
            bool(important),
            normalized_value,
            normalized_range.key if normalized_range is not None else None,
        )
        if signature in self._declaration_signatures:
            raise StyleCatalogError(f"Duplicate authored declaration in rule {self.rule_id}: {normalized_name}")

        declaration = Declaration(
            declaration_id=declaration_id,
            rule_id=self.rule_id,
            name=normalized_name,
            value_text=normalized_value,
            syntax=syntax,
            important=important,
            declaration_order=declaration_order,
            source_range=normalized_range,
            covered_longhands=tuple(covered_longhands),
        )
        self._declarations_by_id[declaration.declaration_id] = declaration
        self._declaration_ids_in_order.append(declaration.declaration_id)
        self._declaration_ids_by_name[declaration.name].append(declaration.declaration_id)
        self._declaration_orders.add(declaration.declaration_order)
        self._declaration_signatures.add(signature)
        return declaration

    def get_declaration(self, declaration_id: str) -> Declaration | None:
        return self._declarations_by_id.get(_clean_text(declaration_id))

    def get_declarations(self, name: str | None = None) -> tuple[Declaration, ...]:
        if name is None:
            return self.declarations
        ids = self._declaration_ids_by_name.get(_normalize_property_name(name), [])
        return tuple(self._declarations_by_id[item] for item in ids)

    def remove_declaration(self, declaration_id: str) -> None:
        normalized = _clean_text(declaration_id)
        declaration = self._declarations_by_id.pop(normalized, None)
        if declaration is None:
            return
        self._declaration_ids_in_order = [item for item in self._declaration_ids_in_order if item != normalized]
        ids = [item for item in self._declaration_ids_by_name.get(declaration.name, []) if item != normalized]
        if ids:
            self._declaration_ids_by_name[declaration.name] = ids
        else:
            self._declaration_ids_by_name.pop(declaration.name, None)
        self._declaration_orders.discard(declaration.declaration_order)
        signature = (
            declaration.name,
            declaration.important,
            declaration.value_text,
            declaration.source_range.key if declaration.source_range is not None else None,
        )
        self._declaration_signatures.discard(signature)

    def is_grouped(self) -> bool:
        return len(self._selectors) > 1

    def is_root_rule(self) -> bool:
        return any(selector.text == ":root" for selector in self._selectors)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "rule_id": self.rule_id,
            "rule_type": self.rule_type.value,
            "source_kind": self.source_kind.value,
            "selectors": [selector.to_dict() for selector in self.selectors],
            "declarations": [declaration.to_dict() for declaration in self.declarations],
            "used": self.used,
        }
        if self.selector_text is not None:
            payload["selector_text"] = self.selector_text
        if self.source_range is not None:
            payload["source_range"] = self.source_range.to_dict()
        if self.source_order is not None:
            payload["source_order"] = self.source_order
        if self.source_url is not None:
            payload["source_url"] = self.source_url
        if self.owner_element_id is not None:
            payload["owner_element_id"] = self.owner_element_id
        if self.at_context:
            payload["at_context"] = [context.to_dict() for context in self.at_context]
        return payload


class StyleCatalog:
    __slots__ = (
        "_rules_by_id",
        "_rule_ids_in_order",
        "_rule_signatures",
        "_range_signatures",
        "_next_rule_number",
    )

    def __init__(self) -> None:
        self._rules_by_id: dict[str, Rule] = {}
        self._rule_ids_in_order: list[str] = []
        self._rule_signatures: set[tuple[object, ...]] = set()
        self._range_signatures: set[tuple[object, ...]] = set()
        self._next_rule_number = 1

    def __len__(self) -> int:
        return len(self._rule_ids_in_order)

    def __iter__(self):
        return iter(self.rules)

    @property
    def rules(self) -> tuple[Rule, ...]:
        return tuple(self._rules_by_id[item] for item in self._rule_ids_in_order)

    def _rule_signature(self, rule: Rule) -> tuple[object, ...]:
        return (
            rule.source_kind.value,
            rule.source_url,
            rule.owner_element_id,
            rule.selector_text,
            tuple(context.signature_key for context in rule.at_context),
            rule.source_order,
        )

    def _range_signature(self, rule: Rule) -> tuple[object, ...] | None:
        if rule.source_range is None:
            return None
        return (
            rule.source_kind.value,
            rule.source_url,
            rule.owner_element_id,
            rule.source_range.key,
        )

    def add_rule(
        self,
        *,
        rule_type: RuleType | str = RuleType.STYLE,
        source_kind: StyleSourceKind | str = StyleSourceKind.UNKNOWN,
        selectors: Iterable[Selector | str] = (),
        at_context: tuple[AtRuleContext, ...] = (),
        source_range: SourceRange | Mapping[str, object] | None = None,
        source_order: int | None = None,
        source_url: str | None = None,
        owner_element_id: str | None = None,
        rule_id: str | None = None,
    ) -> Rule:
        if rule_id is None:
            rule_id = f"rule-{self._next_rule_number:05d}"
            self._next_rule_number += 1
        rule = Rule(
            rule_id=rule_id,
            rule_type=rule_type,
            source_kind=source_kind,
            at_context=tuple(at_context),
            source_range=_coerce_source_range(source_range),
            source_order=source_order,
            source_url=source_url,
            owner_element_id=owner_element_id,
        )
        for index, selector in enumerate(selectors):
            if isinstance(selector, Selector):
                rule.add_selector(
                    text=selector.text,
                    selector_id=selector.selector_id,
                    order_in_group=selector.order_in_group,
                    used=selector.used,
                    specificity=selector.specificity,
                )
            else:
                rule.add_selector(text=str(selector), order_in_group=index)
        if rule.rule_id in self._rules_by_id:
            raise StyleCatalogError(f"Duplicate rule id: {rule.rule_id}")
        rule_signature = self._rule_signature(rule)
        if rule_signature in self._rule_signatures:
            raise StyleCatalogError(f"Duplicate authored rule signature for {rule.rule_id}")
        range_signature = self._range_signature(rule)
        if range_signature is not None and range_signature in self._range_signatures:
            raise StyleCatalogError(f"Duplicate source range for authored rule {rule.rule_id}")

        self._rules_by_id[rule.rule_id] = rule
        self._rule_ids_in_order.append(rule.rule_id)
        self._rule_signatures.add(rule_signature)
        if range_signature is not None:
            self._range_signatures.add(range_signature)
        return rule

    def get_rule(self, rule_id: str) -> Rule:
        try:
            return self._rules_by_id[_clean_text(rule_id)]
        except KeyError as exc:
            raise StyleCatalogError(f"Rule not found: {rule_id}") from exc

    def get_declaration(
        self,
        declaration_id: str | None = None,
        *,
        rule_id: str | None = None,
        name: str | None = None,
    ) -> Declaration | None:
        normalized = _clean_text(declaration_id)
        if normalized and ":decl-" in normalized:
            rule_id = normalized.split(":decl-", 1)[0]
            rule = self._rules_by_id.get(rule_id)
            if rule is not None:
                declaration = rule.get_declaration(normalized)
                if declaration is not None:
                    return declaration
        if normalized:
            for rule in self.rules:
                declaration = rule.get_declaration(normalized)
                if declaration is not None:
                    return declaration
        if rule_id and name:
            rule = self._rules_by_id.get(_clean_text(rule_id))
            if rule is None:
                return None
            declarations = rule.get_declarations(name)
            return declarations[-1] if declarations else None
        return None

    def root_custom_property_declarations(self) -> tuple[Declaration, ...]:
        declarations: list[Declaration] = []
        for rule in self.rules:
            if not rule.is_root_rule():
                continue
            declarations.extend(declaration for declaration in rule.declarations if declaration.is_variable)
        return tuple(declarations)

    def split_grouped_rule(self, rule_id: str, selector_ids: Iterable[str] | None = None) -> Rule | tuple[Rule, ...]:
        rule = self.get_rule(rule_id)
        if not rule.is_grouped():
            return rule

        selectors = list(rule.selectors)
        if selector_ids is None:
            clones: list[Rule] = []
            keep_selector = selectors[0]
            rule._selectors = [keep_selector]
            rule._selectors_by_id = {keep_selector.selector_id: keep_selector}
            rule._selector_texts = {keep_selector.text}
            rule._selector_orders = {keep_selector.order_in_group}
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
        rule._selectors = list(remaining)
        rule._selectors_by_id = {selector.selector_id: selector for selector in remaining}
        rule._selector_texts = {selector.text for selector in remaining}
        rule._selector_orders = {selector.order_in_group for selector in remaining}
        return self._clone_rule_with_selectors(rule, selected)

    def _clone_rule_with_selectors(self, source_rule: Rule, selectors: tuple[Selector, ...]) -> Rule:
        clone = self.add_rule(
            rule_type=source_rule.rule_type,
            source_kind=source_rule.source_kind,
            selectors=tuple(
                Selector(
                    selector_id=f"selector-{index}",
                    text=selector.text,
                    order_in_group=index,
                    used=selector.used,
                    specificity=selector.specificity,
                )
                for index, selector in enumerate(selectors)
            ),
            at_context=source_rule.at_context,
            source_range=source_rule.source_range,
            source_order=source_rule.source_order,
            source_url=source_rule.source_url,
            owner_element_id=source_rule.owner_element_id,
        )
        for declaration in source_rule.declarations:
            clone.add_declaration(
                name=declaration.name,
                value_text=declaration.value_text,
                syntax=declaration.syntax,
                important=declaration.important,
                declaration_order=declaration.declaration_order,
                source_range=declaration.source_range,
                covered_longhands=declaration.covered_longhands,
            )
        return clone

    def to_dict(self) -> dict[str, object]:
        return {
            "total_rules": len(self),
            "total_declarations": sum(len(rule.declarations) for rule in self.rules),
            "rules": [rule.to_dict() for rule in self.rules],
        }
