from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.element import Element
from engine.domain.models.requestRecords import RequestRecords
from engine.domain.models.session import Session
from engine.domain.models.style import Styles
from engine.domain.models.summary import Summary
from engine.domain.models.token import TokenInventory
from typing_extensions import Self


@dataclass(frozen=True, slots=True)
class RecommendationsPayload:
    items: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    summary: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": list(self.items),
            "summary": self.summary,
        }

class PipelineContext:
    def __init__(self) -> None:
        self.session = Session()
        self.page_builder: PageBuilder | None = None
        self.dom_tree: Element | None = None

        self.color_scheme = ColorScheme()
        self.summary = Summary()
        self.style = Styles()
        self.request_records = RequestRecords()
        self.token_inventory = TokenInventory()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if self.page_builder is not None:
            try:
                self.page_builder.close()
            except Exception as close_exc:
                raise RuntimeError(
                    f"unexpected error [{type(close_exc).__name__}]: {close_exc}"
                ) from close_exc
            finally:
                self.page_builder = None
        return False

    def get(self, name: str, default: Any | None = None) -> Any:
        return getattr(self, str(name), default)

    def set(self, name: str, value: Any) -> PipelineContext:
        setattr(self, str(name), value)
        return self

    def has(self, name: str) -> bool:
        return hasattr(self, str(name)) and getattr(self, str(name)) is not None

