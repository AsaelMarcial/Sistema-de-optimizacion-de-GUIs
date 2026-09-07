from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from flask import g, has_app_context

from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.element import DomTree
from engine.domain.models.project_context import ProjectContext
from engine.domain.models.style import Styles
from engine.domain.models.summary import Summary
from engine.domain.models.token import TokenInventory


class PipelineContext:
    __slots__ = (
        "after_root",
        "artifacts_root",
        "before_root",
        "color_scheme",
        "dom_tree",
        "project_context",
        "session_dir",
        "session_id",
        "style",
        "summary",
        "token_inventory",
    )

    def __init__(self) -> None:
        self.session_id = (
            datetime.now().strftime("%Y%m%d%H%M%S") + "_" + uuid.uuid4().hex[:8]
        )
        self.session_dir = (
            Path(__file__).resolve().parents[2]
            / "workspace"
            / "sessions"
            / f"session_{self.session_id}"
        )
        self.before_root = self.session_dir / "before"
        self.after_root = self.session_dir / "after"
        self.artifacts_root = self.session_dir / "artifacts"
        self.dom_tree = DomTree()
        self.color_scheme = ColorScheme()
        self.summary = Summary()
        self.style = Styles()
        self.token_inventory = TokenInventory()
        self.project_context: ProjectContext | None = None
        self._sync_flask_g()

    def __enter__(self) -> "PipelineContext":
        self._sync_flask_g()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if has_app_context():
            for name in (
                "after_root",
                "artifacts_root",
                "before_root",
                "session_id",
                "session_dir",
                "project_context",
                "dom_tree",
                "color_scheme",
                "summary",
                "style",
                "token_inventory",
            ):
                if hasattr(g, name):
                    setattr(self, name, getattr(g, name))

        return False

    def _sync_flask_g(self) -> None:
        if not has_app_context():
            return

        g.session_id = self.session_id
        g.session_dir = self.session_dir
        g.before_root = self.before_root
        g.after_root = self.after_root
        g.artifacts_root = self.artifacts_root
        g.dom_tree = self.dom_tree
        g.color_scheme = self.color_scheme
        g.summary = self.summary
        g.style = self.style
        g.token_inventory = self.token_inventory
        g.project_context = self.project_context

    def get(self, name: str, default=None):
        return getattr(self, str(name), default)

    def set(self, name: str, value) -> None:
        if name == "project_context":
            self.project_context = value
            self.session_id = value.session_id if value is not None else None
            self.session_dir = value.session_dir if value is not None else None
            self.before_root = value.before_root if value is not None else None
            self.after_root = value.after_root if value is not None else None
            self.artifacts_root = value.artifacts_root if value is not None else None
            self._sync_flask_g()
            return

        setattr(self, str(name), value)
        self._sync_flask_g()

    def has(self, name: str) -> bool:
        return hasattr(self, str(name)) and getattr(self, str(name)) is not None
