from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Self


def _normalize_relative_path(value: str) -> str:
    normalized = str(value or "").strip()
    if normalized in {"", "."}:
        return ""
    return normalized


@dataclass(frozen=True, slots=True)
class Session:
    session_id: str
    base_dir: str
    upload_path: str = ""
    project_root_relative_path: str = ""
    html_relative_path: str = ""
    input_html_content: str = ""
    output_html_content: str = ""
    original_capture: Any | None = None
    original_css_overview: dict[str, Any] | None = None
    original_snapshot_metadata: dict[str, Any] = field(default_factory=dict)

    SESSION_DIR_PREFIX: ClassVar[str] = "session_"
    INPUT_DIRNAME: ClassVar[str] = "input"
    OUTPUT_DIRNAME: ClassVar[str] = "output"
    ARTIFACTS_DIRNAME: ClassVar[str] = "artifacts"
    ORIGINAL_SCREENSHOT_NAME: ClassVar[str] = "debug_original.png"
    TRANSFORMED_SCREENSHOT_NAME: ClassVar[str] = "debug_environmental.png"
    PALETTE_PREVIEW_NAME: ClassVar[str] = "palette_preview.png"
    RESULTS_NAME: ClassVar[str] = "results.json"

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", str(self.session_id))
        object.__setattr__(self, "base_dir", str(self.base_dir))
        object.__setattr__(self, "upload_path", str(self.upload_path))
        object.__setattr__(
            self,
            "project_root_relative_path",
            _normalize_relative_path(self.project_root_relative_path),
        )
        object.__setattr__(
            self,
            "html_relative_path",
            _normalize_relative_path(self.html_relative_path),
        )
        object.__setattr__(self, "input_html_content", str(self.input_html_content))
        object.__setattr__(self, "output_html_content", str(self.output_html_content))
        object.__setattr__(
            self,
            "original_snapshot_metadata",
            dict(self.original_snapshot_metadata or {}),
        )

    @classmethod
    def build(
        cls,
        *,
        session_id: str,
        base_dir: str,
        upload_path: str = "",
        project_root_relative_path: str = "",
        html_relative_path: str = "",
        input_html_content: str = "",
        output_html_content: str = "",
        original_capture: Any | None = None,
        original_css_overview: dict[str, Any] | None = None,
        original_snapshot_metadata: dict[str, Any] | None = None,
    ) -> Self:
        return cls(
            session_id=str(session_id),
            base_dir=str(base_dir),
            upload_path=str(upload_path),
            project_root_relative_path=str(project_root_relative_path),
            html_relative_path=str(html_relative_path),
            input_html_content=str(input_html_content),
            output_html_content=str(output_html_content),
            original_capture=original_capture,
            original_css_overview=(
                dict(original_css_overview)
                if original_css_overview is not None
                else None
            ),
            original_snapshot_metadata=dict(original_snapshot_metadata or {}),
        )

    @property
    def session_dirname(self) -> str:
        if self.session_id.startswith(self.SESSION_DIR_PREFIX):
            return self.session_id
        return f"{self.SESSION_DIR_PREFIX}{self.session_id}"

    @property
    def session_dir(self) -> str:
        return str(Path(self.base_dir) / self.session_dirname)

    @property
    def input_dir(self) -> str:
        return str(Path(self.session_dir) / self.INPUT_DIRNAME)

    @property
    def output_dir(self) -> str:
        return str(Path(self.session_dir) / self.OUTPUT_DIRNAME)

    @property
    def artifacts_dir(self) -> str:
        return str(Path(self.session_dir) / self.ARTIFACTS_DIRNAME)

    @property
    def input_base_path(self) -> str:
        return str(Path(self.input_dir) / self.project_root_relative_path) if self.project_root_relative_path else self.input_dir

    @property
    def output_base_path(self) -> str:
        return str(Path(self.output_dir) / self.project_root_relative_path) if self.project_root_relative_path else self.output_dir

    @property
    def input_html_path(self) -> str:
        if not self.html_relative_path:
            return ""
        return str(Path(self.input_base_path) / self.html_relative_path)

    @property
    def input_html_name(self) -> str:
        if self.html_relative_path:
            return Path(self.html_relative_path).name
        return Path(self.upload_path).name

    @property
    def output_html_path(self) -> str:
        if not self.html_relative_path:
            return ""
        return str(Path(self.output_base_path) / self.html_relative_path)

    @property
    def output_html_name(self) -> str:
        return self.input_html_name

    @property
    def original_screenshot_path(self) -> str:
        return str(Path(self.artifacts_dir) / self.ORIGINAL_SCREENSHOT_NAME)

    @property
    def transformed_screenshot_path(self) -> str:
        return str(Path(self.artifacts_dir) / self.TRANSFORMED_SCREENSHOT_NAME)

    @property
    def palette_preview_path(self) -> str:
        return str(Path(self.artifacts_dir) / self.PALETTE_PREVIEW_NAME)

    @property
    def results_json_path(self) -> str:
        return str(Path(self.artifacts_dir) / self.RESULTS_NAME)

    @property
    def bundle_name(self) -> str:
        source_name = Path(self.upload_path or self.input_html_name).name
        if not source_name:
            return ""
        if source_name.lower().endswith(".zip"):
            return source_name
        return f"{Path(source_name).stem}.zip"

    @property
    def bundle_path(self) -> str:
        if not self.bundle_name:
            return ""
        return str(Path(self.artifacts_dir) / self.bundle_name)

    @property
    def download_path(self) -> str:
        if not self.bundle_name:
            return ""
        return f"/sessions/{self.session_dirname}/artifacts/{self.bundle_name}"

    def ensure_exists(self) -> Self:
        Path(self.session_dir).mkdir(parents=True, exist_ok=True)
        Path(self.input_dir).mkdir(parents=True, exist_ok=True)
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        Path(self.artifacts_dir).mkdir(parents=True, exist_ok=True)
        return self

    def validate(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id no puede estar vacio.")
        if not self.base_dir.strip():
            raise ValueError("base_dir no puede estar vacio.")
        if not self.session_dir.strip():
            raise ValueError("session_dir no puede estar vacio.")
        if not self.input_dir.strip():
            raise ValueError("input_dir no puede estar vacio.")
        if not self.output_dir.strip():
            raise ValueError("output_dir no puede estar vacio.")
        if not self.artifacts_dir.strip():
            raise ValueError("artifacts_dir no puede estar vacio.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_dirname": self.session_dirname,
            "base_dir": self.base_dir,
            "session_dir": self.session_dir,
            "input_dir": self.input_dir,
            "output_dir": self.output_dir,
            "artifacts_dir": self.artifacts_dir,
            "upload_path": self.upload_path,
            "project_root_relative_path": self.project_root_relative_path,
            "html_relative_path": self.html_relative_path,
            "input_base_path": self.input_base_path,
            "output_base_path": self.output_base_path,
            "input_html_path": self.input_html_path,
            "input_html_name": self.input_html_name,
            "output_html_path": self.output_html_path,
            "output_html_name": self.output_html_name,
            "input_html_content": self.input_html_content,
            "output_html_content": self.output_html_content,
            "original_screenshot_path": self.original_screenshot_path,
            "transformed_screenshot_path": self.transformed_screenshot_path,
            "palette_preview_path": self.palette_preview_path,
            "results_json_path": self.results_json_path,
            "bundle_name": self.bundle_name,
            "bundle_path": self.bundle_path,
            "download_path": self.download_path,
            "original_capture": self.original_capture,
            "original_css_overview": self.original_css_overview,
            "original_snapshot_metadata": dict(self.original_snapshot_metadata),
        }
