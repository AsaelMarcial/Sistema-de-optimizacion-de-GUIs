from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Iterable, Iterator, Mapping, Self


class TokenState(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    APPLIED = "applied"


class TokenValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ADJUSTED = "adjusted"
    SKIPPED = "skipped"


def _coerce_token_state(value: TokenState | str | None) -> TokenState:
    if isinstance(value, TokenState):
        return value
    return TokenState(str(value or TokenState.DRAFT.value).strip().lower())


def _coerce_validation_status(
    value: TokenValidationStatus | str | None,
) -> TokenValidationStatus:
    if isinstance(value, TokenValidationStatus):
        return value
    return TokenValidationStatus(
        str(value or TokenValidationStatus.PASSED.value).strip().lower()
    )


def _path_string(path: Iterable[str]) -> str:
    return ".".join(str(item) for item in path if str(item))


def _css_variable_name(path: Iterable[str]) -> str:
    return "--" + "-".join(
        str(item).strip().replace(".", "-").replace("_", "-")
        for item in path
        if str(item).strip()
    )


def _design_token_type(property_id: str | None, resolved_value: str) -> str:
    if property_id in {"box-shadow", "text-shadow"}:
        return "shadow"
    if property_id == "background-image":
        return "string"
    if resolved_value.strip().startswith(("rgb", "#", "hsl", "oklch", "color(")):
        return "color"
    return "string"


@dataclass(frozen=True, slots=True)
class TokenValidationModel:
    rule_id: str
    status: TokenValidationStatus
    metrics: Mapping[str, Any] = field(default_factory=dict)
    before: Mapping[str, Any] = field(default_factory=dict)
    after: Mapping[str, Any] = field(default_factory=dict)
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", _coerce_validation_status(self.status))

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        return cls(
            rule_id=str(payload.get("rule_id") or ""),
            status=_coerce_validation_status(payload.get("status")),
            metrics=dict(payload.get("metrics") or {}),
            before=dict(payload.get("before") or {}),
            after=dict(payload.get("after") or {}),
            reason=str(payload["reason"]) if payload.get("reason") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "rule_id": self.rule_id,
            "status": self.status.value,
            "metrics": dict(self.metrics),
            "before": dict(self.before),
            "after": dict(self.after),
        }
        if self.reason is not None:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True, slots=True)
class Token:
    path: tuple[str, ...]
    name: str
    value_kind: str
    resolved_value: str
    alias_to: str | None = None
    value: str = ""
    element_key: str | None = None
    property_id: str | None = None
    value_label: str | None = None
    source_element_ids: tuple[str, ...] = field(default_factory=tuple)
    assigned_element_ids: tuple[str, ...] = field(default_factory=tuple)
    source_property_refs: tuple[str, ...] = field(default_factory=tuple)
    source_color_ids: tuple[str, ...] = field(default_factory=tuple)
    source_style_ids: tuple[str, ...] = field(default_factory=tuple)
    source_palette_ids: tuple[str, ...] = field(default_factory=tuple)
    source_values: tuple[str, ...] = field(default_factory=tuple)
    palette_name: str | None = None
    tone: int | None = None
    state: TokenState = TokenState.DRAFT
    validations: tuple[TokenValidationModel, ...] = field(default_factory=tuple)
    created_by_stage: str | None = None
    annotations: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", _coerce_token_state(self.state))
        object.__setattr__(self, "path", tuple(str(item) for item in self.path if str(item)))
        object.__setattr__(self, "name", self.name or (self.path[-1] if self.path else "token"))

    @classmethod
    def foundation(
        cls,
        *,
        path: tuple[str, ...],
        resolved_value: str,
        palette_name: str | None = None,
        tone: int | None = None,
        source_color_ids: Iterable[str] = (),
        source_palette_ids: Iterable[str] = (),
        created_by_stage: str | None = None,
        annotations: Iterable[str] = (),
    ) -> Self:
        return cls(
            path=path,
            name=path[-1],
            value_kind="foundation",
            resolved_value=resolved_value,
            value=resolved_value,
            palette_name=palette_name,
            tone=tone,
            source_color_ids=tuple(str(item) for item in source_color_ids if str(item)),
            source_palette_ids=tuple(str(item) for item in source_palette_ids if str(item)),
            created_by_stage=created_by_stage,
            annotations=tuple(str(item) for item in annotations if str(item)),
        )

    @classmethod
    def semantic(
        cls,
        *,
        path: tuple[str, ...],
        alias_to: str | None,
        resolved_value: str,
        element_key: str,
        property_id: str,
        value_label: str,
        source_element_ids: Iterable[str] = (),
        assigned_element_ids: Iterable[str] = (),
        source_property_refs: Iterable[str] = (),
        source_color_ids: Iterable[str] = (),
        source_style_ids: Iterable[str] = (),
        source_palette_ids: Iterable[str] = (),
        source_values: Iterable[str] = (),
        palette_name: str | None = None,
        tone: int | None = None,
        created_by_stage: str | None = None,
        annotations: Iterable[str] = (),
    ) -> Self:
        value = f"{{{alias_to}}}" if alias_to else resolved_value
        return cls(
            path=path,
            name=path[-1],
            value_kind="semantic",
            alias_to=alias_to,
            value=value,
            resolved_value=resolved_value,
            element_key=element_key,
            property_id=property_id,
            value_label=value_label,
            source_element_ids=tuple(str(item) for item in source_element_ids if str(item)),
            assigned_element_ids=tuple(str(item) for item in assigned_element_ids if str(item)),
            source_property_refs=tuple(str(item) for item in source_property_refs if str(item)),
            source_color_ids=tuple(str(item) for item in source_color_ids if str(item)),
            source_style_ids=tuple(str(item) for item in source_style_ids if str(item)),
            source_palette_ids=tuple(str(item) for item in source_palette_ids if str(item)),
            source_values=tuple(str(item) for item in source_values if str(item)),
            palette_name=palette_name,
            tone=tone,
            created_by_stage=created_by_stage,
            annotations=tuple(str(item) for item in annotations if str(item)),
        )

    @classmethod
    def component(
        cls,
        *,
        path: tuple[str, ...],
        alias_to: str | None,
        resolved_value: str,
        property_id: str,
        value_label: str,
        source_element_ids: Iterable[str] = (),
        assigned_element_ids: Iterable[str] = (),
        source_property_refs: Iterable[str] = (),
        source_color_ids: Iterable[str] = (),
        source_style_ids: Iterable[str] = (),
        source_palette_ids: Iterable[str] = (),
        source_values: Iterable[str] = (),
        palette_name: str | None = None,
        tone: int | None = None,
        created_by_stage: str | None = None,
        annotations: Iterable[str] = (),
    ) -> Self:
        value = f"{{{alias_to}}}" if alias_to else resolved_value
        return cls(
            path=path,
            name=path[-1],
            value_kind="component",
            alias_to=alias_to,
            value=value,
            resolved_value=resolved_value,
            element_key=path[1] if len(path) > 1 else None,
            property_id=property_id,
            value_label=value_label,
            source_element_ids=tuple(str(item) for item in source_element_ids if str(item)),
            assigned_element_ids=tuple(str(item) for item in assigned_element_ids if str(item)),
            source_property_refs=tuple(str(item) for item in source_property_refs if str(item)),
            source_color_ids=tuple(str(item) for item in source_color_ids if str(item)),
            source_style_ids=tuple(str(item) for item in source_style_ids if str(item)),
            source_palette_ids=tuple(str(item) for item in source_palette_ids if str(item)),
            source_values=tuple(str(item) for item in source_values if str(item)),
            palette_name=palette_name,
            tone=tone,
            created_by_stage=created_by_stage,
            annotations=tuple(str(item) for item in annotations if str(item)),
        )

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        path = tuple(str(item) for item in (payload.get("path") or ()))
        alias_to = None
        if payload.get("alias_to") is not None:
            alias_to = str(payload["alias_to"])
        elif payload.get("aliases"):
            alias_to = str((payload.get("aliases") or ("",))[0])
        elif payload.get("variable_refs"):
            first_ref = next(iter(payload.get("variable_refs") or ()), None)
            if isinstance(first_ref, Mapping) and first_ref.get("path"):
                alias_to = ".".join(str(item) for item in first_ref.get("path") or ())
        return cls(
            path=path,
            name=str(payload.get("name") or payload.get("token") or (path[-1] if path else "")),
            value_kind=str(payload.get("value_kind") or payload.get("tier") or "semantic"),
            resolved_value=str(payload.get("resolved_value") or payload.get("value") or ""),
            alias_to=alias_to,
            value=str(payload.get("value") or ""),
            element_key=(
                str(payload["element_key"]) if payload.get("element_key") is not None else None
            ),
            property_id=(
                str(payload["property_id"])
                if payload.get("property_id") is not None
                else (
                    str((payload.get("source_property_names") or ("",))[0])
                    if payload.get("source_property_names")
                    else None
                )
            ),
            value_label=(
                str(payload["value_label"]) if payload.get("value_label") is not None else None
            ),
            source_element_ids=tuple(str(item) for item in (payload.get("source_element_ids") or ())),
            assigned_element_ids=tuple(str(item) for item in (payload.get("assigned_element_ids") or ())),
            source_property_refs=tuple(
                str(item) for item in (
                    payload.get("source_property_refs")
                    or payload.get("source_property_names")
                    or ()
                )
            ),
            source_color_ids=tuple(str(item) for item in (payload.get("source_color_ids") or ())),
            source_style_ids=tuple(str(item) for item in (payload.get("source_style_ids") or ())),
            source_palette_ids=tuple(str(item) for item in (payload.get("source_palette_ids") or ())),
            source_values=tuple(str(item) for item in (payload.get("source_values") or ())),
            palette_name=(
                str(payload["palette_name"]) if payload.get("palette_name") is not None else None
            ),
            tone=int(payload["tone"]) if payload.get("tone") is not None else None,
            state=_coerce_token_state(payload.get("state")),
            validations=tuple(
                item if isinstance(item, TokenValidationModel) else TokenValidationModel.build(item)
                for item in (payload.get("validations") or ())
                if isinstance(item, (TokenValidationModel, Mapping))
            ),
            created_by_stage=(
                str(payload["created_by_stage"])
                if payload.get("created_by_stage") is not None
                else None
            ),
            annotations=tuple(str(item) for item in (payload.get("annotations") or ())),
        )

    @property
    def token_id(self) -> str:
        return self.path_string

    @property
    def token(self) -> str:
        return self.name

    @property
    def path_string(self) -> str:
        return _path_string(self.path)

    @property
    def css_variable_name(self) -> str:
        return _css_variable_name(self.path)

    @property
    def is_foundation(self) -> bool:
        return len(self.path) >= 2 and self.path[0] == "glow" and self.path[1] == "color"

    @property
    def is_component(self) -> bool:
        return not self.is_foundation and self.value_kind == "component"

    @property
    def is_semantic(self) -> bool:
        return not self.is_foundation and not self.is_component

    @property
    def is_semantic_alias(self) -> bool:
        return self.is_semantic and bool(self.alias_to)

    @property
    def aliases(self) -> tuple[str, ...]:
        return (self.alias_to,) if self.alias_to else ()

    @property
    def design_token_type(self) -> str:
        return _design_token_type(self.property_id, self.resolved_value)

    @property
    def type(self) -> str:
        return self.design_token_type

    @property
    def assigned_property_names(self) -> tuple[str, ...]:
        if self.property_id:
            return (self.property_id,)
        names = []
        for item in self.source_property_refs:
            if ":" in item:
                names.append(item.split(":")[-1])
            elif item:
                names.append(item)
        return tuple(dict.fromkeys(names).keys())

    @property
    def source_property_names(self) -> tuple[str, ...]:
        return self.assigned_property_names

    @property
    def has_failed_validations(self) -> bool:
        return any(item.status == TokenValidationStatus.FAILED for item in self.validations)

    @property
    def effective_assignment_count(self) -> int:
        if self.assigned_element_ids:
            return len(self.assigned_element_ids)
        return len(self.source_element_ids)

    def with_validation(self, validation: TokenValidationModel | Mapping[str, Any]) -> Self:
        item = validation if isinstance(validation, TokenValidationModel) else TokenValidationModel.build(validation)
        return replace(self, validations=(*self.validations, item))

    def with_alias(
        self,
        alias_to: str | None,
        *,
        resolved_value: str | None = None,
        state: TokenState | str | None = None,
    ) -> Self:
        return replace(
            self,
            alias_to=alias_to,
            value=f"{{{alias_to}}}" if alias_to else (resolved_value or self.resolved_value),
            resolved_value=resolved_value if resolved_value is not None else self.resolved_value,
            state=_coerce_token_state(state) if state is not None else self.state,
        )

    def with_resolved_value(
        self,
        *,
        value: str | None = None,
        resolved_value: str,
        state: TokenState | str | None = None,
    ) -> Self:
        return replace(
            self,
            value=value if value is not None else self.value,
            resolved_value=resolved_value,
            state=_coerce_token_state(state) if state is not None else self.state,
        )

    def with_assignment(
        self,
        *,
        element_ids: Iterable[str] | None = None,
        property_refs: Iterable[str] | None = None,
    ) -> Self:
        merged_element_ids = tuple(
            dict.fromkeys(
                [*self.assigned_element_ids, *(str(item) for item in (element_ids or ()) if str(item))]
            ).keys()
        )
        merged_property_refs = tuple(
            dict.fromkeys(
                [*self.source_property_refs, *(str(item) for item in (property_refs or ()) if str(item))]
            ).keys()
        )
        return replace(
            self,
            assigned_element_ids=merged_element_ids,
            source_property_refs=merged_property_refs,
        )

    def with_sources(
        self,
        *,
        element_ids: Iterable[str] | None = None,
        color_ids: Iterable[str] | None = None,
        style_ids: Iterable[str] | None = None,
        palette_ids: Iterable[str] | None = None,
        values: Iterable[str] | None = None,
        property_refs: Iterable[str] | None = None,
    ) -> Self:
        return replace(
            self,
            source_element_ids=tuple(
                dict.fromkeys(
                    [*self.source_element_ids, *(str(item) for item in (element_ids or ()) if str(item))]
                ).keys()
            ),
            source_color_ids=tuple(
                dict.fromkeys(
                    [*self.source_color_ids, *(str(item) for item in (color_ids or ()) if str(item))]
                ).keys()
            ),
            source_style_ids=tuple(
                dict.fromkeys(
                    [*self.source_style_ids, *(str(item) for item in (style_ids or ()) if str(item))]
                ).keys()
            ),
            source_palette_ids=tuple(
                dict.fromkeys(
                    [*self.source_palette_ids, *(str(item) for item in (palette_ids or ()) if str(item))]
                ).keys()
            ),
            source_values=tuple(
                dict.fromkeys(
                    [*self.source_values, *(str(item) for item in (values or ()) if str(item))]
                ).keys()
            ),
            source_property_refs=tuple(
                dict.fromkeys(
                    [*self.source_property_refs, *(str(item) for item in (property_refs or ()) if str(item))]
                ).keys()
            ),
        )

    def metadata_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "token_id": self.token_id,
            "path": list(self.path),
            "name": self.name,
            "token": self.name,
            "value_kind": self.value_kind,
            "resolved_value": self.resolved_value,
            "state": self.state.value,
            "source_element_ids": list(self.source_element_ids),
            "assigned_element_ids": list(self.assigned_element_ids),
            "source_property_refs": list(self.source_property_refs),
            "source_color_ids": list(self.source_color_ids),
            "source_style_ids": list(self.source_style_ids),
            "source_palette_ids": list(self.source_palette_ids),
            "source_values": list(self.source_values),
            "validations": [item.to_dict() for item in self.validations],
            "annotations": list(self.annotations),
        }
        if self.alias_to is not None:
            payload["alias_to"] = self.alias_to
        if self.value:
            payload["value"] = self.value
        if self.element_key is not None:
            payload["element_key"] = self.element_key
        if self.property_id is not None:
            payload["property_id"] = self.property_id
        if self.value_label is not None:
            payload["value_label"] = self.value_label
        if self.palette_name is not None:
            payload["palette_name"] = self.palette_name
        if self.tone is not None:
            payload["tone"] = self.tone
        if self.created_by_stage is not None:
            payload["created_by_stage"] = self.created_by_stage
        return payload

    def to_design_token_dict(self) -> dict[str, Any]:
        value = self.value or (f"{{{self.alias_to}}}" if self.alias_to else self.resolved_value)
        return {
            "$type": self.design_token_type,
            "$value": value,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.metadata_dict()
        payload["css_variable_name"] = self.css_variable_name
        payload["design_token_type"] = self.design_token_type
        return payload


@dataclass(frozen=True, slots=True)
class TokenInventory:
    entries: tuple[Token, ...] = field(default_factory=tuple)

    @classmethod
    def build(cls, payloads: Iterable[Token | Mapping[str, Any]] | None) -> Self:
        if not payloads:
            return cls()
        deduped: dict[str, Token] = {}
        for payload in payloads:
            token = payload if isinstance(payload, Token) else Token.build(payload)
            if not token.token_id:
                continue
            deduped[token.token_id] = token
        ordered = tuple(sorted(deduped.values(), key=lambda item: (item.path_string, item.token_id)))
        return cls(entries=ordered)

    def __iter__(self) -> Iterator[Token]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def entry_by_id(self, token_id: str) -> Token | None:
        return next((entry for entry in self.entries if entry.token_id == token_id), None)

    def with_entries(self, payloads: Iterable[Token | Mapping[str, Any]]) -> Self:
        return type(self).build(payloads)

    def to_rows(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.entries]

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for token in self.entries:
            current = payload
            for segment in token.path[:-1]:
                current = current.setdefault(segment, {})
            current[token.path[-1]] = token.to_design_token_dict()
        return payload


TokenModel = Token
TokenInventoryModel = TokenInventory
