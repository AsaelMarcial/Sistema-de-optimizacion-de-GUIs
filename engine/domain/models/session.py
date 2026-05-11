from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path, PurePosixPath
from typing import ClassVar, Iterable
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SESSIONS_BASE_DIR = Path(
    os.environ.get("GUI_OPT_SESSIONS_DIR", PROJECT_ROOT / "workspace" / "sessions")
).resolve()
SESSION_PREFIX = "session_"

_SESSION_AREAS = {"before", "after", "artifacts"}


def _new_session_id() -> str:
    return uuid.uuid4().hex[:8]


@dataclass(frozen=True, slots=True)
class FilePath:
    relative_path: Path
    kind: str = ""

    def __post_init__(self) -> None:
        path = Path(self.relative_path)
        if path.is_absolute():
            raise ValueError("FilePath debe ser relativo.")

        kind = str(self.kind or "").strip().lower()
        if not kind:
            kind = "file" if path.suffix else "directory"
        if kind not in {"file", "directory"}:
            raise ValueError("FilePath.kind debe ser 'file' o 'directory'.")

        object.__setattr__(self, "relative_path", Path() if path == Path(".") else path)
        object.__setattr__(self, "kind", kind)

    @classmethod
    def from_physical(cls, path: str | Path, *, relative_to: str | Path) -> "FilePath":
        physical = Path(path)
        base = Path(relative_to)
        kind = "directory" if physical.is_dir() else "file"
        return cls(physical.relative_to(base), kind)

    @classmethod
    def from_zip_member(cls, path: str | PurePosixPath, *, is_dir: bool = False) -> "FilePath":
        pure = PurePosixPath(str(path).replace("\\", "/"))
        return cls(Path(*pure.parts), "directory" if is_dir else "file")

    @property
    def name(self) -> str:
        return self.relative_path.name

    @property
    def suffix(self) -> str:
        return "" if self.kind == "directory" else self.relative_path.suffix.lower()

    @property
    def parent(self) -> Path:
        return self.relative_path.parent

    @property
    def parts(self) -> tuple[str, ...]:
        return self.relative_path.parts

    def with_parent(self, parent: str | Path) -> "FilePath":
        parent_path = Path(parent)
        if parent_path == Path():
            return self
        return FilePath(parent_path / self.relative_path, self.kind)

    def resolve_from(self, base: str | Path) -> Path:
        return (Path(base) / self.relative_path).resolve()


@dataclass(slots=True)
class Session:
    session_id: str = field(default_factory=_new_session_id)
    base_dir: Path = SESSIONS_BASE_DIR
    file_paths: tuple[FilePath, ...] = field(default_factory=tuple)

    SESSION_PREFIX: ClassVar[str] = SESSION_PREFIX

    def __post_init__(self) -> None:
        session_id = str(self.session_id or "").strip()
        if not session_id:
            raise ValueError("session_id no puede estar vacio.")
        self.session_id = session_id
        self.base_dir = Path(self.base_dir).resolve()
        self.file_paths = tuple(self.file_paths)

    def build_path(self, area: str, file_path: FilePath | None = None) -> Path:
        area_name = str(area or "").strip().lower()
        if area_name not in _SESSION_AREAS:
            raise ValueError(f"Area de sesion no permitida: {area}.")

        root = self._area_root(area_name)
        if file_path is None:
            return root.resolve()
        return file_path.resolve_from(root)

    def add_file_path(self, file_path: FilePath) -> None:
        if file_path not in self.file_paths:
            self.file_paths = (*self.file_paths, file_path)

    def set_file_paths(self, file_paths: Iterable[FilePath]) -> None:
        unique: list[FilePath] = []
        for file_path in file_paths:
            if file_path not in unique:
                unique.append(file_path)
        self.file_paths = tuple(unique)

    def project_root_file_path(self) -> FilePath:
        roots = {
            path.parts[0]
            for path in self.file_paths
            if path.kind == "directory" and path.parts
        }
        if len(roots) == 1:
            return FilePath(next(iter(roots)), "directory")
        return FilePath(Path(), "directory")

    def _dirname(self) -> str:
        if self.session_id.startswith(self.SESSION_PREFIX):
            return self.session_id
        return f"{self.SESSION_PREFIX}{self.session_id}"

    def _root(self) -> Path:
        return (self.base_dir / self._dirname()).resolve()

    def _area_root(self, area: str) -> Path:
        return (self._root() / area).resolve()


BEFORE_SCREENSHOT = FilePath("before.png")
AFTER_SCREENSHOT = FilePath("after.png")
PALETTE_PREVIEW = FilePath("palette_preview.png")
