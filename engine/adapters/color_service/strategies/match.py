from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Protocol, cast

from coloraide.everything import ColorAll

RGB_INPUT_RE = re.compile(r"^\s*rgba?\(", re.IGNORECASE)
HEX_COLOR_RE = re.compile(
    r"^\s*#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ColorMatchStrategy:
    name: str = "css"
    pattern: re.Pattern[str] | None = None

    def supports(self, value: str) -> bool:
        if not value:
            return False
        normalized = value.strip()
        if not normalized:
            return False
        if self.pattern is None:
            return True
        return self.pattern.match(normalized) is not None

    def parse(self, value: str) -> ColorAll | None:
        if not self.supports(value):
            return None
        try:
            return ColorAll(value.strip())
        except Exception:
            return None

    def find(self, text: str) -> tuple[tuple[int, int, str], ...]:
        source = str(text or "")
        if not source:
            return ()

        matches: list[tuple[int, int, str]] = []
        index = 0
        length = len(source)
        while index < length:
            match = ColorAll.match(source, start=index)
            if match is None:
                index += 1
                continue
            token = source[match.start : match.end].strip()
            if token:
                matches.append((match.start, match.end, token))
            index = max(match.end, index + 1)
        return tuple(matches)

    def extract(self, text: str) -> tuple[str, ...]:
        values: list[str] = []
        for _start, _end, token in self.find(text):
            if token and token not in values:
                values.append(token)
        return tuple(values)


class _MatchRegistryProtocol(Protocol):
    match_strategy: str

    def get_match(self, name: str) -> ColorMatchStrategy:
        ...


class MatchOperationsMixin:
    def find_matches(
        self,
        text: str,
        *,
        strategy_name: str | None = None,
    ) -> tuple[tuple[int, int, str], ...]:
        registry = cast(_MatchRegistryProtocol, self)
        matcher = registry.get_match(strategy_name or registry.match_strategy)
        return tuple(matcher.find(text))

    def match_color(self, value: str, *, strategy_name: str) -> ColorAll | None:
        registry = cast(_MatchRegistryProtocol, self)
        matcher = registry.get_match(strategy_name)
        return matcher.parse(value)
