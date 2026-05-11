from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.domain.enums.scope.context_keys import ContextKey, ContextKeyLike, ContextRoot
from engine.pipeline.debug_trace import DebugTrace

_ALLOWED_ROOT_KEYS = {root.value for root in ContextRoot}
_VALUE_KEY = "__value__"


@dataclass(frozen=True, slots=True)
class RecommendationsPayload:
    items: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": list(self.items),
            "summary": self.summary,
        }


class MissingContextKeysError(ValueError):
    pass


@dataclass(slots=True)
class PipelineContext:
    trace: DebugTrace = field(default_factory=lambda: DebugTrace(enabled=True))
    error: str | None = None
    _state: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def get(self, key: ContextKeyLike, default: Any | None = None) -> Any:
        current: Any = self._state
        for part in self._parts(key):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        if isinstance(current, dict) and _VALUE_KEY in current:
            return current[_VALUE_KEY]
        return current

    def set(self, key: ContextKeyLike, value: Any) -> "PipelineContext":
        current = self._state
        parts = self._parts(key)
        if parts[0] not in _ALLOWED_ROOT_KEYS:
            raise ValueError(
                f"Namespace de PipelineContext no permitido: '{parts[0]}'."
            )
        for part in parts[:-1]:
            next_value = current.get(part)
            if not isinstance(next_value, dict):
                next_value = {_VALUE_KEY: next_value} if next_value is not None else {}
                current[part] = next_value
            current = next_value
        existing_value = current.get(parts[-1])
        if isinstance(existing_value, dict):
            existing_value[_VALUE_KEY] = value
        else:
            current[parts[-1]] = value
        return self

    def has(self, key: ContextKeyLike) -> bool:
        sentinel = object()
        return self.get(key, sentinel) is not sentinel

    def require(self, *keys: ContextKeyLike) -> "PipelineContext":
        missing = tuple(key for key in keys if not self.has(key) or self.get(key) is None)
        if missing:
            raise MissingContextKeysError(
                f"Faltan claves requeridas en PipelineContext: {', '.join(missing)}"
            )
        return self

    def delete(self, key: ContextKeyLike) -> None:
        current: Any = self._state
        parts = self._parts(key)
        for part in parts[:-1]:
            if not isinstance(current, dict) or part not in current:
                return
            current = current[part]
        if isinstance(current, dict):
            current.pop(parts[-1], None)

    def snapshot(self) -> dict[str, Any]:
        return self._clone(self._state)

    def set_error(self, message: str) -> "PipelineContext":
        self.error = message
        return self

    @staticmethod
    def _parts(key: ContextKeyLike) -> tuple[str, ...]:
        raw_key = key.value if isinstance(key, ContextKey) else str(key)
        normalized = tuple(part.strip() for part in raw_key.split(".") if part.strip())
        if not normalized:
            raise ValueError("La clave del contexto no puede estar vacia.")
        return normalized

    @classmethod
    def _clone(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: cls._clone(item) for key, item in value.items()}
        if isinstance(value, list):
            return [cls._clone(item) for item in value]
        if isinstance(value, tuple):
            return tuple(cls._clone(item) for item in value)
        return value
