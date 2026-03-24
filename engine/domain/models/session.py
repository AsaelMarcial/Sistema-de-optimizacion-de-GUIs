from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterator, Mapping, Self


class SessionDirectoryKind(StrEnum):
    INPUT = "input"
    OUTPUT = "output"
    ARTIFACTS = "artifacts"


@dataclass(frozen=True, slots=True)
class SessionDirectoryModel:
    session_id: str
    session_dirname: str
    kind: SessionDirectoryKind
    root_dir: str
    path: str

    @classmethod
    def build(
        cls,
        *,
        session_id: str,
        session_dirname: str,
        kind: SessionDirectoryKind | str,
        root_dir: str,
        name: str | None = None,
    ) -> Self:
        resolved_kind = SessionDirectoryKind(str(kind))
        directory_name = str(name or resolved_kind.value)
        return cls(
            session_id=session_id,
            session_dirname=session_dirname,
            kind=resolved_kind,
            root_dir=str(root_dir),
            path=str(Path(root_dir) / directory_name),
        )

    @property
    def name(self) -> str:
        return Path(self.path).name

    def ensure_exists(self) -> Self:
        Path(self.path).mkdir(parents=True, exist_ok=True)
        return self

    def exists(self) -> bool:
        return Path(self.path).exists()

    def validate(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id no puede estar vacio.")
        if not self.session_dirname.strip():
            raise ValueError("session_dirname no puede estar vacio.")
        if not self.root_dir.strip():
            raise ValueError("root_dir no puede estar vacio.")
        if not self.path.strip():
            raise ValueError("path no puede estar vacio.")

    def join(self, *parts: str) -> str:
        return str(Path(self.path).joinpath(*parts))

    def contains(self, candidate_path: str) -> bool:
        directory = Path(self.path).resolve()
        candidate = Path(candidate_path).resolve()
        try:
            candidate.relative_to(directory)
        except ValueError:
            return False
        return True

    def to_dict(self) -> dict[str, str]:
        return {
            "session_id": self.session_id,
            "session_dirname": self.session_dirname,
            "kind": self.kind.value,
            "root_dir": self.root_dir,
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class SessionModel:
    session_id: str
    session_dirname: str
    base_dir: str
    session_dir: str
    input: SessionDirectoryModel
    output: SessionDirectoryModel
    artifacts: SessionDirectoryModel

    @classmethod
    def build(
        cls,
        *,
        session_id: str,
        session_dirname: str,
        base_dir: str,
        input_dirname: str = SessionDirectoryKind.INPUT.value,
        output_dirname: str = SessionDirectoryKind.OUTPUT.value,
        artifacts_dirname: str = SessionDirectoryKind.ARTIFACTS.value,
    ) -> Self:
        session_dir = str(Path(base_dir) / session_dirname)
        return cls(
            session_id=session_id,
            session_dirname=session_dirname,
            base_dir=str(base_dir),
            session_dir=session_dir,
            input=SessionDirectoryModel.build(
                session_id=session_id,
                session_dirname=session_dirname,
                kind=SessionDirectoryKind.INPUT,
                root_dir=session_dir,
                name=input_dirname,
            ),
            output=SessionDirectoryModel.build(
                session_id=session_id,
                session_dirname=session_dirname,
                kind=SessionDirectoryKind.OUTPUT,
                root_dir=session_dir,
                name=output_dirname,
            ),
            artifacts=SessionDirectoryModel.build(
                session_id=session_id,
                session_dirname=session_dirname,
                kind=SessionDirectoryKind.ARTIFACTS,
                root_dir=session_dir,
                name=artifacts_dirname,
            ),
        )

    @property
    def input_dir(self) -> str:
        return self.input.path

    @property
    def output_dir(self) -> str:
        return self.output.path

    @property
    def artifacts_dir(self) -> str:
        return self.artifacts.path

    def __iter__(self) -> Iterator[SessionDirectoryModel]:
        yield self.input
        yield self.output
        yield self.artifacts

    def ensure_exists(self) -> Self:
        Path(self.session_dir).mkdir(parents=True, exist_ok=True)
        for directory in self:
            directory.ensure_exists()
        return self

    def validate(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id no puede estar vacio.")
        if not self.session_dirname.strip():
            raise ValueError("session_dirname no puede estar vacio.")
        if not self.base_dir.strip():
            raise ValueError("base_dir no puede estar vacio.")
        if not self.session_dir.strip():
            raise ValueError("session_dir no puede estar vacio.")
        for directory in self:
            directory.validate()

    def directory(self, kind: SessionDirectoryKind | str) -> SessionDirectoryModel:
        resolved_kind = SessionDirectoryKind(str(kind))
        if resolved_kind == SessionDirectoryKind.INPUT:
            return self.input
        if resolved_kind == SessionDirectoryKind.OUTPUT:
            return self.output
        return self.artifacts

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "session_dirname": self.session_dirname,
            "base_dir": self.base_dir,
            "session_dir": self.session_dir,
            "input": self.input.to_dict(),
            "output": self.output.to_dict(),
            "artifacts": self.artifacts.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ArtifactGroupModel:
    snapshot: str | None = None
    screenshot: str | None = None
    pixel_frequencies_raw: str | None = None
    pixel_frequencies_display: str | None = None
    elements_inventory: str | None = None
    styles_inventory: str | None = None
    colors_inventory: str | None = None
    color_scheme: str | None = None
    palette_preview: str | None = None
    results: str | None = None
    extras: Mapping[str, str] | None = None

    @classmethod
    def build(cls, payload: Mapping[str, Any] | None = None) -> Self:
        payload = payload or {}
        return cls(
            snapshot=str(payload["snapshot"]) if payload.get("snapshot") is not None else None,
            screenshot=(
                str(payload["screenshot"])
                if payload.get("screenshot") is not None
                else None
            ),
            pixel_frequencies_raw=(
                str(payload["pixel_frequencies_raw"])
                if payload.get("pixel_frequencies_raw") is not None
                else None
            ),
            pixel_frequencies_display=(
                str(payload["pixel_frequencies_display"])
                if payload.get("pixel_frequencies_display") is not None
                else None
            ),
            elements_inventory=(
                str(payload["elements_inventory"])
                if payload.get("elements_inventory") is not None
                else None
            ),
            styles_inventory=(
                str(payload["styles_inventory"])
                if payload.get("styles_inventory") is not None
                else None
            ),
            colors_inventory=(
                str(payload["colors_inventory"])
                if payload.get("colors_inventory") is not None
                else None
            ),
            color_scheme=(
                str(
                    payload["color_scheme"]
                    if payload.get("color_scheme") is not None
                    else payload.get("palette_analysis")
                )
                if payload.get("color_scheme") is not None
                or payload.get("palette_analysis") is not None
                else None
            ),
            palette_preview=(
                str(payload["palette_preview"])
                if payload.get("palette_preview") is not None
                else None
            ),
            results=str(payload["results"]) if payload.get("results") is not None else None,
            extras={
                str(key): str(value)
                for key, value in dict(payload.get("extras") or {}).items()
            }
            or None,
        )

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if self.snapshot is not None:
            payload["snapshot"] = self.snapshot
        if self.screenshot is not None:
            payload["screenshot"] = self.screenshot
        if self.pixel_frequencies_raw is not None:
            payload["pixel_frequencies_raw"] = self.pixel_frequencies_raw
        if self.pixel_frequencies_display is not None:
            payload["pixel_frequencies_display"] = self.pixel_frequencies_display
        if self.elements_inventory is not None:
            payload["elements_inventory"] = self.elements_inventory
        if self.styles_inventory is not None:
            payload["styles_inventory"] = self.styles_inventory
        if self.colors_inventory is not None:
            payload["colors_inventory"] = self.colors_inventory
        if self.color_scheme is not None:
            payload["color_scheme"] = self.color_scheme
        if self.palette_preview is not None:
            payload["palette_preview"] = self.palette_preview
        if self.results is not None:
            payload["results"] = self.results
        if self.extras:
            payload["extras"] = dict(self.extras)
        return payload


@dataclass(frozen=True, slots=True)
class SessionArtifactsModel:
    directory: SessionDirectoryModel
    original: ArtifactGroupModel
    output: ArtifactGroupModel
    derived: ArtifactGroupModel

    @classmethod
    def build(
        cls,
        *,
        directory: SessionDirectoryModel,
        original: Mapping[str, Any] | ArtifactGroupModel | None = None,
        output: Mapping[str, Any] | ArtifactGroupModel | None = None,
        derived: Mapping[str, Any] | ArtifactGroupModel | None = None,
    ) -> Self:
        return cls(
            directory=directory,
            original=(
                original
                if isinstance(original, ArtifactGroupModel)
                else ArtifactGroupModel.build(original)
            ),
            output=(
                output
                if isinstance(output, ArtifactGroupModel)
                else ArtifactGroupModel.build(output)
            ),
            derived=(
                derived
                if isinstance(derived, ArtifactGroupModel)
                else ArtifactGroupModel.build(derived)
            ),
        )

    @property
    def path(self) -> str:
        return self.directory.path

    def to_dict(self) -> dict[str, Any]:
        return {
            "directory": self.directory.to_dict(),
            "original": self.original.to_dict(),
            "output": self.output.to_dict(),
            "derived": self.derived.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ProjectStateModel:
    directory: SessionDirectoryModel
    base_path: str
    normalized_base_path: str
    html_path: str
    html_name: str
    html_content: str
    upload_path: str | None = None
    download_path: str | None = None
    bundle_path: str | None = None

    @property
    def session_id(self) -> str:
        return self.directory.session_id

    @property
    def session_dirname(self) -> str:
        return self.directory.session_dirname

    @property
    def kind(self) -> SessionDirectoryKind:
        return self.directory.kind

    @property
    def root_dir(self) -> str:
        return self.directory.root_dir

    @property
    def path(self) -> str:
        return self.directory.path

    @classmethod
    def build(
        cls,
        *,
        directory: SessionDirectoryModel,
        base_path: str,
        normalized_base_path: str,
        html_path: str,
        html_name: str,
        html_content: str,
        upload_path: str | None = None,
        download_path: str | None = None,
        bundle_path: str | None = None,
    ) -> Self:
        return cls(
            directory=directory,
            base_path=str(base_path),
            normalized_base_path=str(normalized_base_path),
            html_path=str(html_path),
            html_name=str(html_name),
            html_content=str(html_content),
            upload_path=str(upload_path) if upload_path is not None else None,
            download_path=str(download_path) if download_path is not None else None,
            bundle_path=str(bundle_path) if bundle_path is not None else None,
        )

    def validate(self) -> None:
        self.directory.validate()
        required_fields = {
            "base_path": self.base_path,
            "normalized_base_path": self.normalized_base_path,
            "html_path": self.html_path,
            "html_name": self.html_name,
        }
        for field_name, field_value in required_fields.items():
            if not str(field_value).strip():
                raise ValueError(f"{field_name} no puede estar vacio.")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "directory": self.directory.to_dict(),
            "base_path": self.base_path,
            "normalized_base_path": self.normalized_base_path,
            "html_path": self.html_path,
            "html_name": self.html_name,
            "html_content": self.html_content,
        }
        if self.upload_path is not None:
            payload["upload_path"] = self.upload_path
        if self.download_path is not None:
            payload["download_path"] = self.download_path
        if self.bundle_path is not None:
            payload["bundle_path"] = self.bundle_path
        return payload


@dataclass(frozen=True, slots=True)
class ProjectInputModel:
    session: SessionModel
    upload_path: str
    base_path: str
    normalized_base_path: str
    html_path: str
    html_filename: str
    html_content: str

    @property
    def session_id(self) -> str:
        return self.session.session_id

    @property
    def workspace(self) -> SessionModel:
        return self.session

    def to_project_state(
        self,
        *,
        directory: SessionDirectoryModel | None = None,
        html_path: str | None = None,
        html_content: str | None = None,
        download_path: str | None = None,
        bundle_path: str | None = None,
    ) -> ProjectStateModel:
        return ProjectStateModel.build(
            directory=directory or self.session.input,
            upload_path=self.upload_path,
            base_path=self.base_path,
            normalized_base_path=self.normalized_base_path,
            html_path=html_path or self.html_path,
            html_name=Path(html_path or self.html_path).name,
            html_content=html_content if html_content is not None else self.html_content,
            download_path=download_path,
            bundle_path=bundle_path,
        )

    def validate(self) -> None:
        self.session.validate()
        required_fields = {
            "upload_path": self.upload_path,
            "base_path": self.base_path,
            "normalized_base_path": self.normalized_base_path,
            "html_path": self.html_path,
            "html_filename": self.html_filename,
        }
        for field_name, field_value in required_fields.items():
            if not str(field_value).strip():
                raise ValueError(f"{field_name} no puede estar vacio.")

    @classmethod
    def build(cls, payload: Mapping[str, Any]) -> Self:
        session_payload = payload.get("session") or payload.get("workspace") or {}
        if isinstance(session_payload, SessionModel):
            session = session_payload
        elif isinstance(session_payload, Mapping):
            input_payload = session_payload.get("input") or {}
            output_payload = session_payload.get("output") or {}
            artifacts_payload = session_payload.get("artifacts") or {}
            session = SessionModel(
                session_id=str(session_payload.get("session_id") or ""),
                session_dirname=str(session_payload.get("session_dirname") or ""),
                base_dir=str(session_payload.get("base_dir") or ""),
                session_dir=str(session_payload.get("session_dir") or ""),
                input=(
                    input_payload
                    if isinstance(input_payload, SessionDirectoryModel)
                    else SessionDirectoryModel.build(
                        session_id=str(session_payload.get("session_id") or ""),
                        session_dirname=str(session_payload.get("session_dirname") or ""),
                        kind=input_payload.get("kind") or SessionDirectoryKind.INPUT.value,
                        root_dir=str(session_payload.get("session_dir") or ""),
                        name=input_payload.get("name") or Path(str(input_payload.get("path") or "input")).name,
                    )
                ),
                output=(
                    output_payload
                    if isinstance(output_payload, SessionDirectoryModel)
                    else SessionDirectoryModel.build(
                        session_id=str(session_payload.get("session_id") or ""),
                        session_dirname=str(session_payload.get("session_dirname") or ""),
                        kind=output_payload.get("kind") or SessionDirectoryKind.OUTPUT.value,
                        root_dir=str(session_payload.get("session_dir") or ""),
                        name=output_payload.get("name") or Path(str(output_payload.get("path") or "output")).name,
                    )
                ),
                artifacts=(
                    artifacts_payload
                    if isinstance(artifacts_payload, SessionDirectoryModel)
                    else SessionDirectoryModel.build(
                        session_id=str(session_payload.get("session_id") or ""),
                        session_dirname=str(session_payload.get("session_dirname") or ""),
                        kind=artifacts_payload.get("kind") or SessionDirectoryKind.ARTIFACTS.value,
                        root_dir=str(session_payload.get("session_dir") or ""),
                        name=artifacts_payload.get("name") or Path(str(artifacts_payload.get("path") or "artifacts")).name,
                    )
                ),
            )
        else:
            raise TypeError("session/workspace invalido para ProjectInputModel.build")

        return cls(
            session=session,
            upload_path=str(payload.get("upload_path") or ""),
            base_path=str(payload.get("base_path") or ""),
            normalized_base_path=str(payload.get("normalized_base_path") or ""),
            html_path=str(payload.get("html_path") or ""),
            html_filename=str(payload.get("html_filename") or ""),
            html_content=str(payload.get("html_content") or ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.session.to_dict(),
            "upload_path": self.upload_path,
            "base_path": self.base_path,
            "normalized_base_path": self.normalized_base_path,
            "html_path": self.html_path,
            "html_filename": self.html_filename,
            "html_content": self.html_content,
        }
