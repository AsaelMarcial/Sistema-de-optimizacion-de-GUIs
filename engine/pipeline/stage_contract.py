from __future__ import annotations

from dataclasses import dataclass, field
from os import PathLike
from typing import Any, Callable

from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey, ContextKeyLike

ContextValidator = Callable[[Any], bool]


class PipelineContractError(ValueError):
    pass


def non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def path_like(value: Any) -> bool:
    return isinstance(value, (str, PathLike)) and bool(str(value).strip())


def inventory_nonempty(value: Any) -> bool:
    return hasattr(value, "__len__") and len(value) > 0


def raw_snapshot(value: Any) -> bool:
    return hasattr(value, "metadata") and hasattr(value, "nodes")


@dataclass(frozen=True, slots=True)
class ContextValueSpec:
    key: str
    expected_types: tuple[type[Any], ...] = field(default_factory=tuple)
    allow_none: bool = False
    validator: ContextValidator | None = None
    description: str | None = None

    def validate(self, context: PipelineContext) -> None:
        if not context.has(self.key):
            raise PipelineContractError(f"Falta la clave requerida '{self.key}'.")

        value = context.get(self.key)
        if value is None and not self.allow_none:
            raise PipelineContractError(f"La clave '{self.key}' no permite None.")

        if value is None:
            return

        if self.expected_types and not isinstance(value, self.expected_types):
            expected = ", ".join(sorted(type_.__name__ for type_ in self.expected_types))
            raise PipelineContractError(
                f"La clave '{self.key}' tiene tipo invalido. Esperado: {expected}. "
                f"Actual: {type(value).__name__}."
            )

        if self.validator is not None and not self.validator(value):
            raise PipelineContractError(
                f"La clave '{self.key}' no paso la validacion contractual."
            )


@dataclass(frozen=True, slots=True)
class StageContract:
    name: str
    requires: tuple[ContextValueSpec, ...] = field(default_factory=tuple)
    produces: tuple[ContextValueSpec, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PipelineStage:
    contract: StageContract
    run: Callable[[PipelineContext], PipelineContext]


def context_value(
    key: ContextKeyLike,
    *expected_types: type[Any],
    allow_none: bool = False,
    validator: ContextValidator | None = None,
    description: str | None = None,
) -> ContextValueSpec:
    return ContextValueSpec(
        key=key.value if isinstance(key, ContextKey) else str(key),
        expected_types=expected_types,
        allow_none=allow_none,
        validator=validator,
        description=description,
    )


def validate_requires(context: PipelineContext, contract: StageContract) -> None:
    for spec in contract.requires:
        spec.validate(context)


def validate_produces(context: PipelineContext, contract: StageContract) -> None:
    for spec in contract.produces:
        spec.validate(context)
