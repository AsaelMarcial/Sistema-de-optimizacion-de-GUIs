from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Iterator, Mapping, Self

from engine.domain.enums.scope.css_properties import CSS_PROPERTY_SHORTHANDS, get_css_property
from engine.domain.enums.types.style import (
    DeclarationSyntax,
    RuleOrigin,
    RuleType,
    StyleKind,
    StyleOrigin,
    StyleResolutionStatus,
    StyleUsageStatus,
)

_RULE_ID_RE = re.compile(r"^rule-(\d+)$")
_DECLARATION_ID_RE = re.compile(r"^declaration-(\d+)$")
_GENERIC_SHORTHANDS: dict[str, tuple[str, ...]] = {
    "margin": ("margin-top", "margin-right", "margin-bottom", "margin-left"),
    "padding": ("padding-top", "padding-right", "padding-bottom", "padding-left"),
    "inset": ("top", "right", "bottom", "left"),
}


class StyleCatalogError(Exception):
    """Error del modelo de estilos CSS."""


def _clean_text(value: object | None) -> str:
    return str(value or "").strip()


def _normalize_property_name(value: object | None) -> str:
    normalized = _clean_text(value).lower()
    if not normalized:
        return ""
    property_spec = get_css_property(normalized)
    return property_spec.value if property_spec is not None else normalized


def _normalize_selectors(selectors: Iterable[object] | None) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for selector in selectors or ():
        clean = _clean_text(selector)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
    return tuple(result)


def _unique_strings(values: Iterable[object] | None) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for item in values or ():
        normalized = _normalize_property_name(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return tuple(result)


def _coerce_style_kind(value: StyleKind | str | None) -> StyleKind | None:
    if value is None:
        return None
    if isinstance(value, StyleKind):
        return value
    normalized = _clean_text(value).lower()
    if not normalized:
        return None
    if normalized == "matched":
        normalized = StyleKind.EMBEDDED.value
    if normalized == "attributes":
        normalized = StyleKind.INLINE.value
    return StyleKind(normalized)


def _coerce_style_origin(value: StyleOrigin | str | None) -> StyleOrigin | None:
    if value is None:
        return None
    if isinstance(value, StyleOrigin):
        return value
    normalized = _clean_text(value).lower()
    return StyleOrigin(normalized) if normalized else None


def _coerce_style_usage_status(
    value: StyleUsageStatus | str | None,
) -> StyleUsageStatus:
    if isinstance(value, StyleUsageStatus):
        return value
    normalized = _clean_text(value).lower() or StyleUsageStatus.UNKNOWN.value
    return StyleUsageStatus(normalized)


def _coerce_style_resolution_status(
    value: StyleResolutionStatus | str | None,
) -> StyleResolutionStatus | None:
    if value is None:
        return None
    if isinstance(value, StyleResolutionStatus):
        return value
    normalized = _clean_text(value).lower()
    return StyleResolutionStatus(normalized) if normalized else None


def _coerce_rule_origin(value: RuleOrigin | str | None) -> RuleOrigin | None:
    if value is None:
        return None
    if isinstance(value, RuleOrigin):
        return value
    normalized = _clean_text(value).lower()
    return RuleOrigin(normalized) if normalized else None


def _coerce_rule_type(value: RuleType | str | None) -> RuleType:
    if isinstance(value, RuleType):
        return value
    normalized = _clean_text(value).lower()
    if not normalized:
        return RuleType.STYLE
    try:
        return RuleType(normalized)
    except ValueError:
        return RuleType.UNKNOWN


def _coerce_declaration_syntax(
    value: DeclarationSyntax | str | None,
    *,
    name: str,
    covered_longhands: tuple[str, ...],
) -> DeclarationSyntax:
    if name.startswith("--"):
        return DeclarationSyntax.CUSTOM_PROPERTY
    if isinstance(value, DeclarationSyntax):
        return value
    normalized = _clean_text(value).lower()
    if normalized:
        return DeclarationSyntax(normalized)
    if covered_longhands:
        return DeclarationSyntax.SHORTHAND
    return DeclarationSyntax.LONGHAND


def _infer_rule_origin(
    *,
    rule_origin: RuleOrigin | str | None = None,
    kind: StyleKind | str | None = None,
    source_url: str | None = None,
) -> RuleOrigin:
    explicit = _coerce_rule_origin(rule_origin)
    if explicit is not None:
        return explicit
    compat_kind = _coerce_style_kind(kind)
    if compat_kind == StyleKind.INLINE:
        return RuleOrigin.INLINE
    if compat_kind == StyleKind.EXTERNAL or _clean_text(source_url):
        return RuleOrigin.EXTERNAL
    if compat_kind == StyleKind.USER_AGENT:
        return RuleOrigin.USER_AGENT
    return RuleOrigin.EMBEDDED


def _infer_kind(
    *,
    origin: RuleOrigin,
    compat_kind: StyleKind | str | None,
) -> StyleKind:
    normalized = _coerce_style_kind(compat_kind)
    if normalized is not None:
        return normalized
    if origin == RuleOrigin.INLINE:
        return StyleKind.INLINE
    if origin == RuleOrigin.EXTERNAL:
        return StyleKind.EXTERNAL
    if origin == RuleOrigin.USER_AGENT:
        return StyleKind.USER_AGENT
    return StyleKind.EMBEDDED


def _covered_longhands_for_property(property_name: str) -> tuple[str, ...]:
    return tuple(
        CSS_PROPERTY_SHORTHANDS.get(
            property_name,
            _GENERIC_SHORTHANDS.get(property_name, ()),
        )
    )


def _selector_text_from_selectors(selectors: tuple[str, ...]) -> str | None:
    return ", ".join(selectors) if selectors else None


def _next_child_id_values(current: list[str], new_id: str) -> list[str]:
    if new_id and new_id not in current:
        current.append(new_id)
    return current


@dataclass(frozen=True, slots=True)
class SourceRange:
    start_line: int
    start_column: int
    end_line: int
    end_column: int
    start_offset: int | None = None
    end_offset: int | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any] | "SourceRange" | None) -> "SourceRange | None":
        if payload is None:
            return None
        if isinstance(payload, cls):
            return payload

        if "start" in payload or "end" in payload:
            start = payload.get("start") or {}
            end = payload.get("end") or {}
            return cls(
                start_line=int(start.get("line") or 0),
                start_column=int(start.get("column") or 0),
                end_line=int(end.get("line") or 0),
                end_column=int(end.get("column") or 0),
                start_offset=(
                    int(start["offset"])
                    if start.get("offset") is not None
                    else None
                ),
                end_offset=(
                    int(end["offset"])
                    if end.get("offset") is not None
                    else None
                ),
            )

        return cls(
            start_line=int(payload.get("start_line") or payload.get("startLine") or 0),
            start_column=int(payload.get("start_column") or payload.get("startColumn") or 0),
            end_line=int(payload.get("end_line") or payload.get("endLine") or 0),
            end_column=int(payload.get("end_column") or payload.get("endColumn") or 0),
            start_offset=(
                int(payload["start_offset"])
                if payload.get("start_offset") is not None
                else (
                    int(payload["startOffset"])
                    if payload.get("startOffset") is not None
                    else None
                )
            ),
            end_offset=(
                int(payload["end_offset"])
                if payload.get("end_offset") is not None
                else (
                    int(payload["endOffset"])
                    if payload.get("endOffset") is not None
                    else None
                )
            ),
        )

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
        payload: dict[str, int | None] = {
            "start_line": self.start_line,
            "start_column": self.start_column,
            "end_line": self.end_line,
            "end_column": self.end_column,
        }
        if self.start_offset is not None:
            payload["start_offset"] = self.start_offset
        if self.end_offset is not None:
            payload["end_offset"] = self.end_offset
        return payload


StyleSourceRange = SourceRange


@dataclass(frozen=True, slots=True)
class AtRuleContext:
    rule_type: RuleType
    prelude: str | None = None
    source_range: SourceRange | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any] | "AtRuleContext" | None) -> "AtRuleContext | None":
        if payload is None:
            return None
        if isinstance(payload, cls):
            return payload
        return cls(
            rule_type=_coerce_rule_type(payload.get("rule_type") or payload.get("ruleType")),
            prelude=_clean_text(payload.get("prelude")) or None,
            source_range=SourceRange.build(payload.get("source_range") or payload.get("sourceRange")),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule_type": self.rule_type.value,
        }
        if self.prelude is not None:
            payload["prelude"] = self.prelude
        if self.source_range is not None:
            payload["source_range"] = self.source_range.to_dict()
        return payload


@dataclass(frozen=True, slots=True)
class ResolvedStyleValue:
    computed_value: str
    style_id: str | None = None
    kind: StyleKind | None = None
    declared_property: str | None = None
    declaration_id: str | None = None
    inherited_from_element_id: str | None = None
    resolution_status: StyleResolutionStatus | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _coerce_style_kind(self.kind))
        object.__setattr__(
            self,
            "declared_property",
            _normalize_property_name(self.declared_property) or None,
        )
        object.__setattr__(
            self,
            "resolution_status",
            _coerce_style_resolution_status(self.resolution_status),
        )

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            computed_value=str(payload.get("computed_value") or ""),
            style_id=(
                _clean_text(payload.get("rule_id"))
                or _clean_text(payload.get("style_id"))
                or None
            ),
            kind=_coerce_style_kind(payload.get("kind")),
            declared_property=_normalize_property_name(payload.get("declared_property")) or None,
            declaration_id=_clean_text(payload.get("declaration_id")) or None,
            inherited_from_element_id=_clean_text(payload.get("inherited_from_element_id")) or None,
            resolution_status=_coerce_style_resolution_status(payload.get("resolution_status")),
        )

    @property
    def rule_id(self) -> str | None:
        return self.style_id

    def is_resolved(self) -> bool:
        return self.resolution_status == StyleResolutionStatus.EXACT_MATCH

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "computed_value": self.computed_value,
        }
        if self.style_id is not None:
            payload["rule_id"] = self.style_id
            payload["style_id"] = self.style_id
        if self.kind is not None:
            payload["kind"] = self.kind.value
        if self.declared_property is not None:
            payload["declared_property"] = self.declared_property
        if self.declaration_id is not None:
            payload["declaration_id"] = self.declaration_id
        if self.inherited_from_element_id is not None:
            payload["inherited_from_element_id"] = self.inherited_from_element_id
        if self.resolution_status is not None:
            payload["resolution_status"] = self.resolution_status.value
        return payload


class Declaration:
    __slots__ = (
        "_declaration_id",
        "_rule_id",
        "_name",
        "_code_value",
        "_source_range",
        "_important",
        "_syntax",
        "_authored_text",
        "_covered_longhands",
        "_computed_values",
        "_used",
        "_overridden",
        "_implicit",
        "_declaration_order",
        "_usage_status",
        "_element_usage_count",
        "_used_by_element_ids",
        "_parse_status",
    )

    def __init__(
        self,
        *,
        declaration_id: str | None,
        rule_id: str,
        name: str,
        code_value: str,
        source_range: SourceRange | None = None,
        important: bool = False,
        syntax: DeclarationSyntax | str | None = None,
        authored_text: str | None = None,
        covered_longhands: Iterable[object] | None = None,
        computed_values: Mapping[str, str] | None = None,
        used: bool = False,
        overridden: bool = False,
        implicit: bool = False,
        declaration_order: int | None = None,
        usage_status: StyleUsageStatus | str | None = None,
        element_usage_count: int = 0,
        used_by_element_ids: Iterable[object] | None = None,
        parse_status: str | None = None,
    ) -> None:
        normalized_name = _normalize_property_name(name)
        normalized_longhands = _unique_strings(
            covered_longhands if covered_longhands is not None else _covered_longhands_for_property(normalized_name)
        )

        self._declaration_id = _clean_text(declaration_id) or None
        self._rule_id = _clean_text(rule_id)
        self._name = normalized_name
        self._code_value = str(code_value or "")
        self._source_range = SourceRange.build(source_range)
        self._important = bool(important)
        self._syntax = _coerce_declaration_syntax(
            syntax,
            name=normalized_name,
            covered_longhands=normalized_longhands,
        )
        self._authored_text = _clean_text(authored_text) or None
        self._covered_longhands = normalized_longhands
        self._computed_values = {
            _normalize_property_name(key): str(value)
            for key, value in dict(computed_values or {}).items()
            if _normalize_property_name(key)
        }
        self._used = bool(used)
        self._overridden = bool(overridden)
        self._implicit = bool(implicit)
        self._declaration_order = declaration_order
        self._usage_status = _coerce_style_usage_status(usage_status)
        self._element_usage_count = int(element_usage_count or 0)
        self._used_by_element_ids = tuple(
            str(item).strip()
            for item in (used_by_element_ids or ())
            if str(item).strip()
        )
        self._parse_status = _clean_text(parse_status) or None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> "Declaration":
        return cls(
            declaration_id=_clean_text(payload.get("declaration_id")) or None,
            rule_id=_clean_text(payload.get("rule_id")),
            name=_normalize_property_name(payload.get("name") or payload.get("property_name")),
            code_value=str(payload.get("code_value") or payload.get("value") or payload.get("raw_value") or ""),
            source_range=SourceRange.build(payload.get("source_range")),
            important=bool(payload.get("important", False)),
            syntax=payload.get("syntax"),
            authored_text=(
                str(payload["authored_text"])
                if payload.get("authored_text") is not None
                else None
            ),
            covered_longhands=(
                payload.get("covered_longhands")
                or payload.get("longhand_properties")
                or ()
            ),
            computed_values=dict(payload.get("computed_values") or {}),
            used=bool(payload.get("used", False)),
            overridden=bool(payload.get("overridden", False)),
            implicit=bool(payload.get("implicit", False)),
            declaration_order=(
                int(payload["declaration_order"])
                if payload.get("declaration_order") is not None
                else None
            ),
            usage_status=payload.get("usage_status"),
            element_usage_count=int(payload.get("element_usage_count") or 0),
            used_by_element_ids=tuple(payload.get("used_by_element_ids") or ()),
            parse_status=(
                str(payload["parse_status"])
                if payload.get("parse_status") is not None
                else None
            ),
        )

    def __len__(self) -> int:
        return len(self._computed_values)

    @property
    def declaration_id(self) -> str | None:
        return self._declaration_id

    @property
    def rule_id(self) -> str:
        return self._rule_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> str:
        return self._code_value

    @property
    def code_value(self) -> str:
        return self._code_value

    @property
    def source_range(self) -> SourceRange | None:
        return self._source_range

    @property
    def important(self) -> bool:
        return self._important

    @property
    def syntax(self) -> DeclarationSyntax:
        return self._syntax

    @property
    def authored_text(self) -> str | None:
        return self._authored_text

    @property
    def covered_longhands(self) -> tuple[str, ...]:
        return self._covered_longhands

    @property
    def longhand_properties(self) -> tuple[str, ...]:
        return self._covered_longhands

    @property
    def computed_values(self) -> dict[str, str]:
        return dict(self._computed_values)

    @property
    def used(self) -> bool:
        return self._used

    @property
    def overridden(self) -> bool:
        return self._overridden

    @property
    def implicit(self) -> bool:
        return self._implicit

    @property
    def declaration_order(self) -> int | None:
        return self._declaration_order

    @property
    def usage_status(self) -> StyleUsageStatus:
        return self._usage_status

    @property
    def element_usage_count(self) -> int:
        return self._element_usage_count

    @property
    def used_by_element_ids(self) -> tuple[str, ...]:
        return self._used_by_element_ids

    @property
    def parse_status(self) -> str | None:
        return self._parse_status

    @property
    def is_variable(self) -> bool:
        return self._name.startswith("--")

    def matches_property(self, property_name: str) -> bool:
        return self._name == _normalize_property_name(property_name)

    def covers_property(self, property_name: str) -> bool:
        normalized = _normalize_property_name(property_name)
        return normalized == self._name or normalized in self._covered_longhands

    def with_identifier(self, declaration_id: str) -> "Declaration":
        self._declaration_id = _clean_text(declaration_id) or None
        return self

    def with_usage(
        self,
        *,
        used_by_element_ids: tuple[str, ...],
        usage_status: StyleUsageStatus | str,
        element_usage_count: int,
    ) -> "Declaration":
        self._used_by_element_ids = tuple(
            str(item).strip() for item in used_by_element_ids if str(item).strip()
        )
        self._usage_status = _coerce_style_usage_status(usage_status)
        self._element_usage_count = int(element_usage_count or 0)
        self._used = bool(self._used_by_element_ids)
        return self

    def set_computed_value(self, property_name: str, computed_value: str) -> None:
        normalized = _normalize_property_name(property_name)
        if normalized:
            self._computed_values[normalized] = str(computed_value or "")
            self._used = True

    def mark_used(self) -> None:
        self._used = True

    def mark_overridden(self) -> None:
        self._overridden = True

    def to_builder_dict(self) -> dict[str, Any]:
        payload = self.to_dict()
        return payload

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self._name,
            "value": self._code_value,
            "code_value": self._code_value,
            "rule_id": self._rule_id,
            "syntax": self._syntax.value,
            "used": self._used,
            "overridden": self._overridden,
            "usage_status": self._usage_status.value,
        }
        if self._declaration_id is not None:
            payload["declaration_id"] = self._declaration_id
        if self._source_range is not None:
            payload["source_range"] = self._source_range.to_dict()
        if self._important:
            payload["important"] = True
        if self._implicit:
            payload["implicit"] = True
        if self._declaration_order is not None:
            payload["declaration_order"] = self._declaration_order
        if self._authored_text is not None:
            payload["authored_text"] = self._authored_text
        if self._covered_longhands:
            payload["covered_longhands"] = list(self._covered_longhands)
            payload["longhand_properties"] = list(self._covered_longhands)
        if self._computed_values:
            payload["computed_values"] = dict(self._computed_values)
        if self._parse_status is not None:
            payload["parse_status"] = self._parse_status
        return payload


StyleDeclaration = Declaration


class Rule:
    __slots__ = (
        "_rule_id",
        "_origin",
        "_selectors",
        "_selector_text",
        "_rule_type",
        "_source_range",
        "_at_context",
        "_parent_rule_id",
        "_child_rule_ids",
        "_declarations",
        "_used",
        "_stylesheet_id",
        "_source_url",
        "_kind",
        "_cascade_origin",
        "_layer_name",
        "_layer_order",
        "_owner_node_id",
        "_owner_tag_name",
        "_attribute_name",
        "_style_tag_index",
        "_source_name",
    )

    def __init__(
        self,
        *,
        rule_id: str,
        origin: RuleOrigin,
        selectors: Iterable[object] | None = None,
        selector_text: str | None = None,
        rule_type: RuleType | str | None = None,
        source_range: SourceRange | Mapping[str, Any] | None = None,
        at_context: Iterable[AtRuleContext | Mapping[str, Any]] | None = None,
        parent_rule_id: str | None = None,
        stylesheet_id: str | None = None,
        source_url: str | None = None,
        kind: StyleKind | str | None = None,
        cascade_origin: StyleOrigin | str | None = None,
        layer_name: str | None = None,
        layer_order: int | None = None,
        owner_node_id: str | None = None,
        owner_tag_name: str | None = None,
        attribute_name: str | None = None,
        style_tag_index: int | None = None,
        source_name: str | None = None,
        used: bool = False,
    ) -> None:
        self._rule_id = _clean_text(rule_id)
        self._origin = _coerce_rule_origin(origin) or RuleOrigin.EMBEDDED
        self._selectors = _normalize_selectors(selectors)
        self._selector_text = _clean_text(selector_text) or _selector_text_from_selectors(self._selectors)
        self._rule_type = _coerce_rule_type(rule_type)
        self._source_range = SourceRange.build(source_range)
        self._at_context = tuple(
            context
            if isinstance(context, AtRuleContext)
            else AtRuleContext.build(context)
            for context in (at_context or ())
            if context is not None
        )
        self._parent_rule_id = _clean_text(parent_rule_id) or None
        self._child_rule_ids: list[str] = []
        self._declarations: list[Declaration] = []
        self._used = bool(used)
        self._stylesheet_id = _clean_text(stylesheet_id) or None
        self._source_url = _clean_text(source_url) or None
        self._kind = _infer_kind(origin=self._origin, compat_kind=kind)
        self._cascade_origin = (
            _coerce_style_origin(cascade_origin)
            if cascade_origin is not None
            else (
                StyleOrigin.USER_AGENT
                if self._origin == RuleOrigin.USER_AGENT
                else StyleOrigin.AUTHOR
            )
        )
        self._layer_name = _clean_text(layer_name) or None
        self._layer_order = int(layer_order) if layer_order is not None else None
        self._owner_node_id = _clean_text(owner_node_id) or None
        self._owner_tag_name = _clean_text(owner_tag_name).lower() or None
        self._attribute_name = _clean_text(attribute_name) or None
        self._style_tag_index = int(style_tag_index) if style_tag_index is not None else None
        self._source_name = _clean_text(source_name) or None

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> "Rule":
        rule_origin = _infer_rule_origin(
            rule_origin=payload.get("rule_origin"),
            kind=payload.get("kind"),
            source_url=payload.get("source_url"),
        )
        rule_cls: type[Rule] = {
            RuleOrigin.INLINE: InlineRule,
            RuleOrigin.EXTERNAL: ExternalRule,
            RuleOrigin.USER_AGENT: UserAgentRule,
            RuleOrigin.EMBEDDED: EmbeddedRule,
        }[rule_origin]
        rule = rule_cls(
            rule_id=_clean_text(payload.get("rule_id") or payload.get("style_id")),
            origin=rule_origin,
            selectors=tuple(payload.get("selectors") or ()),
            selector_text=payload.get("selector_text"),
            rule_type=payload.get("rule_type"),
            source_range=SourceRange.build(payload.get("source_range")),
            at_context=tuple(payload.get("at_context") or ()),
            parent_rule_id=payload.get("parent_rule_id"),
            stylesheet_id=payload.get("style_sheet_id") or payload.get("stylesheet_id"),
            source_url=payload.get("source_url"),
            kind=payload.get("kind"),
            cascade_origin=payload.get("cascade_origin") or payload.get("origin"),
            layer_name=payload.get("layer_name"),
            layer_order=payload.get("layer_order"),
            owner_node_id=payload.get("owner_node_id"),
            owner_tag_name=payload.get("owner_tag_name"),
            attribute_name=payload.get("attribute_name"),
            style_tag_index=payload.get("style_tag_index"),
            source_name=payload.get("source_name"),
            used=bool(payload.get("used", False)),
        )
        for child_rule_id in payload.get("child_rule_ids") or ():
            rule.add_child_rule_id(str(child_rule_id))
        for declaration_payload in payload.get("declarations") or ():
            if not isinstance(declaration_payload, Mapping):
                continue
            rule.add_declaration(
                name=declaration_payload.get("name") or declaration_payload.get("property_name"),
                code_value=declaration_payload.get("code_value")
                or declaration_payload.get("value")
                or declaration_payload.get("raw_value")
                or "",
                source_range=SourceRange.build(declaration_payload.get("source_range")),
                important=bool(declaration_payload.get("important", False)),
                syntax=declaration_payload.get("syntax"),
                authored_text=declaration_payload.get("authored_text"),
                covered_longhands=(
                    declaration_payload.get("covered_longhands")
                    or declaration_payload.get("longhand_properties")
                    or ()
                ),
                declaration_id=declaration_payload.get("declaration_id"),
                implicit=bool(declaration_payload.get("implicit", False)),
                declaration_order=declaration_payload.get("declaration_order"),
                usage_status=declaration_payload.get("usage_status"),
                element_usage_count=int(declaration_payload.get("element_usage_count") or 0),
                used_by_element_ids=tuple(declaration_payload.get("used_by_element_ids") or ()),
                parse_status=declaration_payload.get("parse_status"),
                computed_values=dict(declaration_payload.get("computed_values") or {}),
                used=bool(declaration_payload.get("used", False)),
                overridden=bool(declaration_payload.get("overridden", False)),
            )
        return rule

    @property
    def rule_id(self) -> str:
        return self._rule_id

    @property
    def style_id(self) -> str:
        return self._rule_id

    @property
    def origin(self) -> RuleOrigin:
        return self._origin

    @property
    def cascade_origin(self) -> StyleOrigin | None:
        return self._cascade_origin

    @property
    def kind(self) -> StyleKind:
        return self._kind

    @property
    def selectors(self) -> tuple[str, ...]:
        return self._selectors

    @property
    def selector_text(self) -> str | None:
        return self._selector_text

    @property
    def rule_type(self) -> RuleType:
        return self._rule_type

    @property
    def source_range(self) -> SourceRange | None:
        return self._source_range

    @property
    def at_context(self) -> tuple[AtRuleContext, ...]:
        return self._at_context

    @property
    def parent_rule_id(self) -> str | None:
        return self._parent_rule_id

    @property
    def child_rule_ids(self) -> tuple[str, ...]:
        return tuple(self._child_rule_ids)

    @property
    def declarations(self) -> tuple[Declaration, ...]:
        return tuple(self._declarations)

    @property
    def used(self) -> bool:
        return self._used

    @property
    def stylesheet_id(self) -> str | None:
        return self._stylesheet_id

    @property
    def style_sheet_id(self) -> str | None:
        return self._stylesheet_id

    @property
    def source_url(self) -> str | None:
        return self._source_url

    @property
    def layer_name(self) -> str | None:
        return self._layer_name

    @property
    def layer_order(self) -> int | None:
        return self._layer_order

    @property
    def owner_node_id(self) -> str | None:
        return self._owner_node_id

    @property
    def owner_tag_name(self) -> str | None:
        return self._owner_tag_name

    @property
    def attribute_name(self) -> str | None:
        return self._attribute_name

    @property
    def style_tag_index(self) -> int | None:
        return self._style_tag_index

    @property
    def source_name(self) -> str | None:
        return self._source_name

    @property
    def is_editable(self) -> bool:
        return self._origin != RuleOrigin.USER_AGENT

    def __iter__(self) -> Iterator[Declaration]:
        return iter(self._declarations)

    def __len__(self) -> int:
        return len(self._declarations)

    def add_child_rule_id(self, rule_id: str) -> None:
        normalized = _clean_text(rule_id)
        if normalized:
            _next_child_id_values(self._child_rule_ids, normalized)

    def add_declaration(
        self,
        *,
        name: str,
        code_value: str,
        source_range: SourceRange | Mapping[str, Any] | None = None,
        important: bool = False,
        syntax: DeclarationSyntax | str | None = None,
        authored_text: str | None = None,
        covered_longhands: Iterable[object] | None = None,
        declaration_id: str | None = None,
        implicit: bool = False,
        declaration_order: int | None = None,
        usage_status: StyleUsageStatus | str | None = None,
        element_usage_count: int = 0,
        used_by_element_ids: Iterable[object] | None = None,
        parse_status: str | None = None,
        computed_values: Mapping[str, str] | None = None,
        used: bool = False,
        overridden: bool = False,
    ) -> Declaration:
        normalized_range = SourceRange.build(source_range)
        normalized_name = _normalize_property_name(name)
        normalized_value = str(code_value or "")
        for current in self._declarations:
            if declaration_id and current.declaration_id == _clean_text(declaration_id):
                return current
            same_range = (
                normalized_range is not None
                and current.source_range is not None
                and current.source_range.key == normalized_range.key
            )
            same_fingerprint = (
                current.name == normalized_name
                and current.value == normalized_value
                and current.important == bool(important)
                and current.implicit == bool(implicit)
                and (
                    (current.source_range is None and normalized_range is None)
                    or same_range
                )
            )
            if same_range or same_fingerprint:
                return current

        declaration = Declaration(
            declaration_id=_clean_text(declaration_id) or None,
            rule_id=self._rule_id,
            name=normalized_name,
            code_value=normalized_value,
            source_range=normalized_range,
            important=important,
            syntax=syntax,
            authored_text=authored_text,
            covered_longhands=covered_longhands,
            computed_values=computed_values,
            used=used,
            overridden=overridden,
            implicit=implicit,
            declaration_order=declaration_order,
            usage_status=usage_status,
            element_usage_count=element_usage_count,
            used_by_element_ids=used_by_element_ids,
            parse_status=parse_status,
        )
        self._declarations.append(declaration)
        return declaration

    def get_declaration(self, property_name: str) -> Declaration | None:
        normalized = _normalize_property_name(property_name)
        matches = [declaration for declaration in self._declarations if declaration.name == normalized]
        return matches[-1] if matches else None

    def get_declaration_by_range(self, source_range: SourceRange) -> Declaration | None:
        return next(
            (
                declaration
                for declaration in self._declarations
                if declaration.source_range is not None and declaration.source_range.key == source_range.key
            ),
            None,
        )

    def get_declarations_for_property(self, property_name: str) -> tuple[Declaration, ...]:
        normalized = _normalize_property_name(property_name)
        return tuple(
            declaration
            for declaration in self._declarations
            if declaration.covers_property(normalized)
        )

    def find_declaration_covering(self, property_name: str) -> Declaration | None:
        matches = self.get_declarations_for_property(property_name)
        return matches[-1] if matches else None

    def declaration_for(self, property_name: str) -> Declaration | None:
        return self.find_declaration_covering(property_name)

    def with_declarations(self, declarations: Iterable[Declaration]) -> "Rule":
        self._declarations = list(declarations)
        return self

    def mark_used(self) -> None:
        self._used = True

    def get_source_key(self) -> tuple[Any, ...]:
        return (
            self._origin.value,
            tuple(self._selectors),
            self._selector_text,
            self._rule_type.value,
            self._source_range.key if self._source_range is not None else None,
            tuple(tuple(sorted(context.to_dict().items())) for context in self._at_context),
            self._parent_rule_id,
            self._stylesheet_id,
            self._source_url,
            self._layer_name,
            self._layer_order,
            self._owner_node_id,
            self._attribute_name,
            self._style_tag_index,
            self._source_name,
        )

    def signature(self) -> tuple[Any, ...]:
        return (
            self._kind,
            self._cascade_origin,
            self._stylesheet_id,
            self._selector_text,
            tuple(sorted((self._source_range.to_dict() if self._source_range else {}).items())),
            self._layer_name,
            self._layer_order,
            self._source_url,
            tuple(
                (
                    declaration.name,
                    declaration.value,
                    declaration.important,
                    declaration.implicit,
                )
                for declaration in self._declarations
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule_id": self._rule_id,
            "style_id": self._rule_id,
            "rule_origin": self._origin.value,
            "origin": self._cascade_origin.value if self._cascade_origin is not None else None,
            "kind": self._kind.value,
            "rule_type": self._rule_type.value,
            "used": self._used,
            "is_editable": self.is_editable,
            "declarations": [declaration.to_dict() for declaration in self._declarations],
        }
        if self._selectors:
            payload["selectors"] = list(self._selectors)
        if self._selector_text is not None:
            payload["selector_text"] = self._selector_text
        if self._source_range is not None:
            payload["source_range"] = self._source_range.to_dict()
        if self._at_context:
            payload["at_context"] = [context.to_dict() for context in self._at_context]
        if self._parent_rule_id is not None:
            payload["parent_rule_id"] = self._parent_rule_id
        if self._child_rule_ids:
            payload["child_rule_ids"] = list(self._child_rule_ids)
        if self._stylesheet_id is not None:
            payload["style_sheet_id"] = self._stylesheet_id
            payload["stylesheet_id"] = self._stylesheet_id
        if self._source_url is not None:
            payload["source_url"] = self._source_url
        if self._layer_name is not None:
            payload["layer_name"] = self._layer_name
        if self._layer_order is not None:
            payload["layer_order"] = self._layer_order
        if self._owner_node_id is not None:
            payload["owner_node_id"] = self._owner_node_id
        if self._owner_tag_name is not None:
            payload["owner_tag_name"] = self._owner_tag_name
        if self._attribute_name is not None:
            payload["attribute_name"] = self._attribute_name
        if self._style_tag_index is not None:
            payload["style_tag_index"] = self._style_tag_index
        if self._source_name is not None:
            payload["source_name"] = self._source_name
        return payload


class InlineRule(Rule):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("origin", RuleOrigin.INLINE)
        kwargs.setdefault("kind", StyleKind.INLINE)
        kwargs.setdefault("attribute_name", "style")
        super().__init__(**kwargs)


class EmbeddedRule(Rule):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("origin", RuleOrigin.EMBEDDED)
        kwargs.setdefault("kind", StyleKind.EMBEDDED)
        super().__init__(**kwargs)


class ExternalRule(Rule):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("origin", RuleOrigin.EXTERNAL)
        kwargs.setdefault("kind", StyleKind.EXTERNAL)
        super().__init__(**kwargs)


class UserAgentRule(Rule):
    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("origin", RuleOrigin.USER_AGENT)
        kwargs.setdefault("kind", StyleKind.USER_AGENT)
        kwargs.setdefault("cascade_origin", StyleOrigin.USER_AGENT)
        kwargs.setdefault("source_name", "chromium-user-agent")
        super().__init__(**kwargs)


StyleRule = Rule


class StyleCatalog:
    def __init__(self, entries: Iterable[Rule] | None = None) -> None:
        self._rules_by_id: dict[str, Rule] = {}
        self._rules_by_source_key: dict[tuple[Any, ...], Rule] = {}
        self._rules_by_range: dict[tuple[Any, ...], list[str]] = {}
        self._rule_ids_by_parent_rule_id: dict[str, list[str]] = {}
        self._rule_ids_by_origin: dict[RuleOrigin, list[str]] = {}
        self._rule_ids_by_stylesheet_id: dict[str, list[str]] = {}
        self._declarations_by_id: dict[str, Declaration] = {}
        self._declaration_ids_by_rule_id: dict[str, list[str]] = {}
        self._declarations_by_range: dict[tuple[Any, ...], list[str]] = {}
        self._entries: list[Rule] = []
        self._rule_counter = 0
        self._declaration_counter = 0
        for entry in entries or ():
            self._register_rule(entry)
            for declaration in entry.declarations:
                self._register_declaration(entry, declaration)

    @property
    def entries(self) -> tuple[Rule, ...]:
        return tuple(self._entries)

    @property
    def rules(self) -> tuple[Rule, ...]:
        return self.entries

    @property
    def declarations(self) -> tuple[Declaration, ...]:
        return tuple(
            declaration
            for declaration_id in (
                declaration_id
                for rule in self._entries
                for declaration_id in self._declaration_ids_by_rule_id.get(rule.rule_id, ())
            )
            if (declaration := self._declarations_by_id.get(declaration_id)) is not None
        )

    @classmethod
    def build(cls, payloads: Any) -> "StyleCatalog":
        if not payloads:
            return cls()
        raw_rules = payloads.get("rules") if isinstance(payloads, Mapping) else payloads
        catalog = cls()
        for payload in raw_rules or ():
            if isinstance(payload, Rule):
                rule = payload
            elif isinstance(payload, Mapping):
                rule = Rule.build(payload)
            else:
                continue
            catalog._register_rule(rule)
            for declaration in rule.declarations:
                catalog._register_declaration(rule, declaration)
        return catalog

    @classmethod
    def build_from_aggregate(
        cls,
        aggregate: Mapping[tuple[Any, ...], Mapping[str, Any]],
    ) -> tuple["StyleCatalog", dict[tuple[Any, ...], str]]:
        if not aggregate:
            return cls(), {}

        sorted_keys = sorted(
            aggregate,
            key=lambda key: (
                aggregate[key]["_sort_key"],
                aggregate[key].get("selector_text") or "",
                str(aggregate[key].get("kind") or ""),
            ),
        )
        style_ids_by_key = {
            key: f"style-{index}"
            for index, key in enumerate(sorted_keys, start=1)
        }
        catalog = cls()

        for key in sorted_keys:
            aggregate_entry = aggregate[key]
            style_id = style_ids_by_key[key]
            used_by_element_ids = tuple(
                sorted(str(item) for item in aggregate_entry.get("node_ids") or ())
            )
            rule_origin = _infer_rule_origin(
                kind=aggregate_entry.get("kind"),
                source_url=aggregate_entry.get("source_url"),
            )
            rule_cls: type[Rule] = {
                RuleOrigin.INLINE: InlineRule,
                RuleOrigin.EXTERNAL: ExternalRule,
                RuleOrigin.USER_AGENT: UserAgentRule,
                RuleOrigin.EMBEDDED: EmbeddedRule,
            }[rule_origin]
            rule = rule_cls(
                rule_id=style_id,
                origin=rule_origin,
                selector_text=aggregate_entry.get("selector_text"),
                rule_type=RuleType.STYLE,
                source_range=SourceRange.build(aggregate_entry.get("source_range")),
                stylesheet_id=aggregate_entry.get("style_sheet_id"),
                source_url=aggregate_entry.get("source_url"),
                kind=aggregate_entry.get("kind"),
                cascade_origin=aggregate_entry.get("origin"),
                layer_name=aggregate_entry.get("layer_name"),
                layer_order=aggregate_entry.get("layer_order"),
                used=bool(used_by_element_ids),
            )
            catalog._register_rule(rule)

            for index, declaration_payload in enumerate(aggregate_entry.get("declarations") or (), start=1):
                if not isinstance(declaration_payload, Mapping):
                    continue
                declaration = rule.add_declaration(
                    name=declaration_payload.get("name") or declaration_payload.get("property_name"),
                    code_value=declaration_payload.get("value") or declaration_payload.get("code_value") or "",
                    important=bool(declaration_payload.get("important", False)),
                    implicit=bool(declaration_payload.get("implicit", False)),
                    declaration_id=f"{style_id}-decl-{index}",
                    declaration_order=declaration_payload.get("declaration_order"),
                    usage_status="used" if used_by_element_ids else "unknown",
                    element_usage_count=len(used_by_element_ids),
                    used_by_element_ids=used_by_element_ids,
                    parse_status=declaration_payload.get("parse_status"),
                    covered_longhands=(
                        declaration_payload.get("covered_longhands")
                        or declaration_payload.get("longhand_properties")
                        or ()
                    ),
                )
                catalog._register_declaration(rule, declaration)

        return catalog, style_ids_by_key

    def __iter__(self) -> Iterator[Rule]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def _sync_rule_counter(self, rule_id: str) -> None:
        match = _RULE_ID_RE.match(rule_id)
        if match:
            self._rule_counter = max(self._rule_counter, int(match.group(1)))

    def _sync_declaration_counter(self, declaration_id: str) -> None:
        match = _DECLARATION_ID_RE.match(declaration_id)
        if match:
            self._declaration_counter = max(self._declaration_counter, int(match.group(1)))

    def _next_rule_id(self) -> str:
        self._rule_counter += 1
        return f"rule-{self._rule_counter:05d}"

    def _next_declaration_id(self) -> str:
        self._declaration_counter += 1
        return f"declaration-{self._declaration_counter:05d}"

    def _register_rule(self, rule: Rule) -> Rule:
        if not rule.rule_id:
            raise StyleCatalogError("Rule id is required.")
        existing = self._rules_by_id.get(rule.rule_id)
        if existing is not None:
            return existing

        source_key = rule.get_source_key()
        existing = self._rules_by_source_key.get(source_key)
        if existing is not None:
            return existing

        self._entries.append(rule)
        self._rules_by_id[rule.rule_id] = rule
        self._rules_by_source_key[source_key] = rule
        self._rule_ids_by_origin.setdefault(rule.origin, []).append(rule.rule_id)
        if rule.parent_rule_id is not None:
            self._rule_ids_by_parent_rule_id.setdefault(rule.parent_rule_id, []).append(rule.rule_id)
        if rule.stylesheet_id is not None:
            self._rule_ids_by_stylesheet_id.setdefault(rule.stylesheet_id, []).append(rule.rule_id)
        if rule.source_range is not None:
            self._rules_by_range.setdefault(rule.source_range.key, []).append(rule.rule_id)
        self._sync_rule_counter(rule.rule_id)
        return rule

    def _register_declaration(self, rule: Rule, declaration: Declaration) -> Declaration:
        if declaration.declaration_id is None:
            declaration.with_identifier(self._next_declaration_id())
        existing_id = declaration.declaration_id or ""
        existing = self._declarations_by_id.get(existing_id)
        if existing is not None:
            return existing

        self._declarations_by_id[existing_id] = declaration
        self._declaration_ids_by_rule_id.setdefault(rule.rule_id, []).append(existing_id)
        if declaration.source_range is not None:
            self._declarations_by_range.setdefault(declaration.source_range.key, []).append(existing_id)
        self._sync_declaration_counter(existing_id)
        return declaration

    def add_inline_rule(
        self,
        *,
        owner_node_id: str,
        owner_tag_name: str | None = None,
        attribute_name: str = "style",
        source_range: SourceRange | Mapping[str, Any] | None = None,
        selector_text: str | None = None,
    ) -> InlineRule:
        rule = InlineRule(
            rule_id=self._next_rule_id(),
            origin=RuleOrigin.INLINE,
            selector_text=selector_text,
            source_range=SourceRange.build(source_range),
            owner_node_id=owner_node_id,
            owner_tag_name=owner_tag_name,
            attribute_name=attribute_name,
        )
        return self._register_rule(rule)  # type: ignore[return-value]

    def add_embedded_rule(
        self,
        *,
        selectors: Iterable[object] | None = None,
        selector_text: str | None = None,
        stylesheet_id: str | None = None,
        style_tag_index: int | None = None,
        source_range: SourceRange | Mapping[str, Any] | None = None,
        rule_type: RuleType | str | None = None,
        at_context: Iterable[AtRuleContext | Mapping[str, Any]] | None = None,
        parent_rule_id: str | None = None,
        layer_name: str | None = None,
        layer_order: int | None = None,
    ) -> EmbeddedRule:
        rule = EmbeddedRule(
            rule_id=self._next_rule_id(),
            origin=RuleOrigin.EMBEDDED,
            selectors=selectors,
            selector_text=selector_text,
            stylesheet_id=stylesheet_id,
            style_tag_index=style_tag_index,
            source_range=SourceRange.build(source_range),
            rule_type=rule_type,
            at_context=at_context,
            parent_rule_id=parent_rule_id,
            layer_name=layer_name,
            layer_order=layer_order,
        )
        registered = self._register_rule(rule)
        if parent_rule_id is not None:
            parent = self.get_rule(parent_rule_id)
            if parent is not None:
                parent.add_child_rule_id(registered.rule_id)
        return registered  # type: ignore[return-value]

    def add_external_rule(
        self,
        *,
        selectors: Iterable[object] | None = None,
        selector_text: str | None = None,
        stylesheet_id: str | None = None,
        source_url: str,
        source_range: SourceRange | Mapping[str, Any] | None = None,
        rule_type: RuleType | str | None = None,
        at_context: Iterable[AtRuleContext | Mapping[str, Any]] | None = None,
        parent_rule_id: str | None = None,
        layer_name: str | None = None,
        layer_order: int | None = None,
    ) -> ExternalRule:
        rule = ExternalRule(
            rule_id=self._next_rule_id(),
            origin=RuleOrigin.EXTERNAL,
            selectors=selectors,
            selector_text=selector_text,
            stylesheet_id=stylesheet_id,
            source_url=source_url,
            source_range=SourceRange.build(source_range),
            rule_type=rule_type,
            at_context=at_context,
            parent_rule_id=parent_rule_id,
            layer_name=layer_name,
            layer_order=layer_order,
        )
        registered = self._register_rule(rule)
        if parent_rule_id is not None:
            parent = self.get_rule(parent_rule_id)
            if parent is not None:
                parent.add_child_rule_id(registered.rule_id)
        return registered  # type: ignore[return-value]

    def add_user_agent_rule(
        self,
        *,
        selectors: Iterable[object] | None = None,
        selector_text: str | None = None,
        source_name: str = "chromium-user-agent",
        source_range: SourceRange | Mapping[str, Any] | None = None,
        rule_type: RuleType | str | None = None,
        at_context: Iterable[AtRuleContext | Mapping[str, Any]] | None = None,
        parent_rule_id: str | None = None,
    ) -> UserAgentRule:
        rule = UserAgentRule(
            rule_id=self._next_rule_id(),
            origin=RuleOrigin.USER_AGENT,
            selectors=selectors,
            selector_text=selector_text,
            source_name=source_name,
            source_range=SourceRange.build(source_range),
            rule_type=rule_type,
            at_context=at_context,
            parent_rule_id=parent_rule_id,
        )
        registered = self._register_rule(rule)
        if parent_rule_id is not None:
            parent = self.get_rule(parent_rule_id)
            if parent is not None:
                parent.add_child_rule_id(registered.rule_id)
        return registered  # type: ignore[return-value]

    def add_rule_declaration(self, rule_id: str, **kwargs: Any) -> Declaration:
        rule = self.get_rule(rule_id)
        if rule is None:
            raise StyleCatalogError(f"Rule not found: {rule_id}")
        declaration = rule.add_declaration(**kwargs)
        return self._register_declaration(rule, declaration)

    def entry_by_id(self, style_id: str) -> Rule | None:
        return self._rules_by_id.get(_clean_text(style_id))

    def get_rule(self, style_id: str) -> Rule | None:
        return self.entry_by_id(style_id)

    def get_rule_by_range(self, source_range: SourceRange | Mapping[str, Any] | None) -> Rule | None:
        range_obj = SourceRange.build(source_range)
        if range_obj is None:
            return None
        rule_ids = self._rules_by_range.get(range_obj.key, ())
        return self._rules_by_id.get(rule_ids[0]) if rule_ids else None

    def declaration_by_id(self, declaration_id: str) -> Declaration | None:
        return self._declarations_by_id.get(_clean_text(declaration_id))

    def get_declaration(self, declaration_id: str) -> Declaration | None:
        return self.declaration_by_id(declaration_id)

    def get_declaration_by_range(
        self,
        source_range: SourceRange | Mapping[str, Any] | None,
        *,
        property_name: str | None = None,
    ) -> Declaration | None:
        range_obj = SourceRange.build(source_range)
        if range_obj is None:
            return None
        normalized_property = _normalize_property_name(property_name) if property_name else None
        for declaration_id in self._declarations_by_range.get(range_obj.key, ()):
            declaration = self._declarations_by_id.get(declaration_id)
            if declaration is None:
                continue
            if normalized_property is None or declaration.covers_property(normalized_property):
                return declaration
        return None

    def get_rules_by_origin(self, origin: RuleOrigin | str) -> tuple[Rule, ...]:
        final_origin = _coerce_rule_origin(origin)
        if final_origin is None:
            return ()
        return tuple(
            self._rules_by_id[rule_id]
            for rule_id in self._rule_ids_by_origin.get(final_origin, ())
            if rule_id in self._rules_by_id
        )

    def get_variables(self) -> tuple[Declaration, ...]:
        variables: list[Declaration] = []
        for rule in self._entries:
            in_root = any(selector == ":root" for selector in rule.selectors)
            for declaration in rule.declarations:
                if declaration.is_variable or in_root:
                    variables.append(declaration)
        return tuple(variables)

    def find_declaration_for_cdp_match(
        self,
        *,
        declaration_range: SourceRange | Mapping[str, Any] | None,
        rule_range: SourceRange | Mapping[str, Any] | None,
        selector_text: str | None = None,
        selectors: Iterable[object] | None = None,
        property_name: str,
        stylesheet_id: str | None = None,
        source_url: str | None = None,
    ) -> Declaration | None:
        normalized_property = _normalize_property_name(property_name)

        if declaration_range is not None:
            declaration = self.get_declaration_by_range(
                declaration_range,
                property_name=normalized_property,
            )
            if declaration is not None:
                return declaration

        if rule_range is not None:
            rule = self.get_rule_by_range(rule_range)
            if rule is not None:
                declaration = rule.find_declaration_covering(normalized_property)
                if declaration is not None:
                    return declaration

        candidate_selectors = _normalize_selectors(selectors)
        selector_candidates = set(candidate_selectors)
        selector_text_clean = _clean_text(selector_text)
        if selector_text_clean:
            selector_candidates.add(selector_text_clean)
        if selector_candidates:
            for rule in self._entries:
                if stylesheet_id and rule.stylesheet_id != _clean_text(stylesheet_id):
                    continue
                if source_url and rule.source_url != _clean_text(source_url):
                    continue
                if rule.selector_text not in selector_candidates and not selector_candidates.intersection(rule.selectors):
                    continue
                declaration = rule.find_declaration_covering(normalized_property)
                if declaration is not None:
                    return declaration

        for rule in self._entries:
            declaration = rule.find_declaration_covering(normalized_property)
            if declaration is not None:
                return declaration
        return None

    def enrich_declaration_from_cdp(
        self,
        *,
        declaration_range: SourceRange | Mapping[str, Any] | None = None,
        rule_range: SourceRange | Mapping[str, Any] | None = None,
        selector_text: str | None = None,
        selectors: Iterable[object] | None = None,
        property_name: str,
        computed_value: str,
        overridden: bool = False,
        stylesheet_id: str | None = None,
        source_url: str | None = None,
    ) -> Declaration | None:
        declaration = self.find_declaration_for_cdp_match(
            declaration_range=declaration_range,
            rule_range=rule_range,
            selector_text=selector_text,
            selectors=selectors,
            property_name=property_name,
            stylesheet_id=stylesheet_id,
            source_url=source_url,
        )
        if declaration is None:
            return None

        declaration.set_computed_value(property_name, computed_value)
        if overridden:
            declaration.mark_overridden()
        else:
            declaration.mark_used()
            rule = self.get_rule(declaration.rule_id)
            if rule is not None:
                rule.mark_used()
        return declaration

    def to_dict(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self._entries]