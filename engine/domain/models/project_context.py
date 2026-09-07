from __future__ import annotations

import fnmatch
import re
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

from flask import g, has_app_context

from engine.utilities.files import copy_directory_tree, save_file

_LOCAL_HOSTS = {"127.0.0.1", "localhost"}
_HTML_MIME_TYPES = {"text/html", "application/xhtml+xml"}
_CSS_MIME_TYPES = {"text/css"}
_SOURCE_FILE_TYPES = {"html", "css", "js", "txt", "xml"}
_VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov", ".webm", ".ogv"}


@dataclass(slots=True, kw_only=True)
class ProjectFile:
    _path: Path
    _mime_type: str = ""
    time: datetime = field(default_factory=datetime.now)
    _resource: Resource | None = field(
        default=None, repr=False, hash=False, compare=False
    )
    _referenced_by: set[ProjectSource] = field(
        default_factory=set, repr=False, hash=False, compare=False
    )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ProjectFile) and self.path == other.path

    def __hash__(self) -> int:
        return hash(self.path)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def absolute_path(self) -> Path:
        if self._path.is_absolute():
            return self._path.resolve()
        if has_app_context():
            return g.before_root.joinpath(self._path).resolve()
        return Path.cwd().joinpath(self._path).resolve()

    @property
    def root_relative_path(self) -> re.Pattern[str]:
        return re.compile(
            fnmatch.translate(self.path.as_posix()),
            re.IGNORECASE,
        )

    @property
    def mime_type(self) -> str:
        return self._mime_type

    @property
    def file_type(self) -> str:
        value = self.mime_type.strip().lower()

        match value:
            case "text/html" | "application/xhtml+xml":
                return "html"
            case "text/css":
                return "css"
            case "text/javascript" | "application/javascript":
                return "js"
            case "text/plain":
                return self.path.suffix.lower().removeprefix(".") or "txt"
            case "text/xml" | "application/xml":
                return "xml"
            case "image/svg+xml" | "image/svg":
                return "svg"
            case mime if mime.startswith("video/"):
                return "video"
            case mime if mime.startswith("image/"):
                return self.path.suffix.lower().removeprefix(".") or "image"
            case _:
                return self.path.suffix.lower().removeprefix(".") or value

    @property
    def runtime_information(self) -> Resource | None:
        return self._resource

    @property
    def is_loaded(self) -> bool:
        return self._resource is not None and self._resource.load_status is True

    @property
    def is_referenced(self) -> bool:
        return bool(self._referenced_by)

    @property
    def referenced_by(self) -> set[ProjectSource]:
        return self._referenced_by

    def bind_resource(self, resource: Resource) -> Resource:
        self._resource = resource
        resource.project_file = self
        return resource

    def add_usage(self, backend_node_id: int) -> None:
        if self._resource is not None:
            self._resource.element_usages.add(int(backend_node_id))


@dataclass(slots=True, kw_only=True, eq=False)
class ProjectAsset(ProjectFile):
    _original_path: Path | None = field(
        default=None, repr=False, hash=False, compare=False
    )
    _versions: set[ProjectAsset] = field(
        default_factory=set, repr=False, hash=False, compare=False
    )

    def __post_init__(self) -> None:
        self._original_path = (
            self.path
            if self._original_path is None and self.file_type == "svg"
            else self._original_path
        )

    @property
    def original_path(self) -> Path:
        return self._original_path or self.path

    @property
    def is_original(self) -> bool:
        return self.original_path == self.path

    @property
    def has_versions(self) -> bool:
        return bool(self._versions)

    @property
    def versions(self) -> list[ProjectAsset]:
        return sorted(self._versions, key=lambda version: version.path.as_posix())

    def add_version(self, content: bytes) -> ProjectAsset:
        if self.file_type != "svg":
            raise ValueError("Solo los assets SVG pueden tener versiones.")
        if not self.is_original:
            raise ValueError("Las versiones deben crearse desde el asset original.")
        project_context = g.project_context
        if project_context is None:
            raise RuntimeError("ProjectAsset no tiene ProjectContext.")

        index = 0
        while True:
            suffix = "-glow" if index == 0 else f"-glow-{index + 1}"
            version_path = self.path.with_stem(f"{self.path.stem}{suffix}")
            version_file = ProjectAsset(
                _path=version_path,
                _mime_type=self.mime_type,
                _original_path=self.original_path,
            )
            if not version_file.absolute_path.exists():
                break
            index += 1

        save_file(version_file.absolute_path, bytes(content))
        version = version_file
        self._versions.add(version)
        project_context.FILES_REGISTRY[version.path] = version
        project_context.GENERATED_FILES_REGISTRY[version.path] = version
        project_context.assets[version.path] = version
        return version

    def version(self, reference: str | Path) -> ProjectAsset:
        reference_path = Path(reference)
        for version in self._versions:
            if (
                version.path == reference_path
                or version.path.name == reference_path.name
            ):
                return version
        raise ValueError(f"No se encontró ninguna versión con el nombre '{reference}'.")


@dataclass(slots=True, kw_only=True, eq=False)
class ProjectSource(ProjectFile):
    _dependencies: set[ProjectFile] = field(
        default_factory=set, repr=False, hash=False, compare=False
    )
    _resources: list[tuple[str, ProjectFile]] = field(
        default_factory=list, repr=False, hash=False, compare=False
    )

    def add_dependency(
        self,
        child_file: ProjectFile,
        reference: str | None = None,
    ) -> ProjectFile:
        if child_file is not self and child_file not in self._dependencies:
            self._dependencies.add(child_file)
            child_file.referenced_by.add(self)

        if reference is not None and (reference, child_file) not in self._resources:
            self._resources.append((reference, child_file))

        return child_file

    @property
    def dependencies(self) -> list[ProjectFile]:
        return sorted(
            self._dependencies,
            key=lambda file: (
                isinstance(file, ProjectAsset),
                file.file_type,
                file.path.name,
            ),
        )

    @property
    def asset_dependencies(self) -> list[ProjectAsset]:
        return [file for file in self.dependencies if isinstance(file, ProjectAsset)]

    @property
    def source_dependencies(self) -> list[ProjectSource]:
        return [file for file in self.dependencies if isinstance(file, ProjectSource)]

    @property
    def resources(self) -> tuple[tuple[str, ProjectFile], ...]:
        return tuple(self._resources)

    def has_dependency(self, reference: str | Path) -> bool:
        related_file = (
            g.project_context.project_file(reference, self)
            if has_app_context() and getattr(g, "project_context", None) is not None
            else None
        )
        return related_file in self._dependencies

    @property
    def get_refs_relative_to_(self) -> list[str]:
        return [reference for reference, _file in self._resources]


@dataclass(slots=True, kw_only=True)
class Resource:
    url: str
    timing: float = 0.0
    resource_type: str = "unknown"
    load_status: bool = False
    message: str | None = ""
    element_usages: set[int] = field(
        default_factory=set, repr=False, hash=False, compare=False
    )
    project_file: ProjectFile | None = field(
        default=None, repr=False, hash=False, compare=False
    )

    def __post_init__(self) -> None:
        if not has_app_context() or getattr(g, "project_context", None) is None:
            return

        project_context = g.project_context
        project_context.RESOURCES_REGISTRY[self.url] = self
        project_file = project_context.project_file(self.real_ref)
        if project_file is not None:
            project_file.bind_resource(self)

    @property
    def is_local(self) -> bool:
        return self.project_file is not None

    @property
    def is_loaded(self) -> bool:
        return self.load_status is True

    @property
    def is_used(self) -> bool:
        return bool(self.element_usages)

    @property
    def real_ref(self) -> Path | str:
        if self.project_file is not None:
            return self.project_file.path

        value = urlsplit(unquote(self.url))
        if value.scheme in {"http", "https"}:
            if value.hostname in _LOCAL_HOSTS:
                return Path(value.path.lstrip("/"))
            return self.url

        if not value.scheme and not value.netloc:
            return Path(value.path)

        return self.url


class ProjectContext:
    __slots__ = (
        "FILES_REGISTRY",
        "GENERATED_FILES_REGISTRY",
        "RESOURCES_REGISTRY",
        "_assets",
        "_existing_dirs",
        "_failed",
        "_glow_style_sheet",
        "_html",
        "_stylesheets",
        "page_url",
        "session_id",
        "session_dir",
    )

    def __init__(
        self,
        files: list[dict[str, str | bytes | Path]],
    ) -> None:

        self.FILES_REGISTRY: dict[Path, ProjectSource | ProjectAsset] = {}
        self.GENERATED_FILES_REGISTRY: dict[
            Path, ProjectSource | ProjectAsset | ProjectFile
        ] = {}
        self.RESOURCES_REGISTRY: dict[str, Resource] = {}
        self._existing_dirs: set[str] = set()
        self._assets: dict[Path, ProjectAsset] = {}
        self._stylesheets: dict[Path, ProjectSource] = {}
        self._failed: list[Path] = []
        self._glow_style_sheet: ProjectSource | None = None
        self._html: ProjectSource | None = None
        self.page_url = ""
        self.session_id = g.session_id
        self.session_dir = g.session_dir

        for file_info in files:
            path = Path(file_info["file_name"])
            mime_type = str(file_info["mime_type"])

            stored_file = (
                ProjectSource(_path=path, _mime_type=mime_type)
                if mime_type in _HTML_MIME_TYPES or mime_type in _CSS_MIME_TYPES
                else ProjectAsset(_path=path, _mime_type=mime_type)
            )

            if (
                not stored_file.absolute_path.exists()
                or not stored_file.absolute_path.is_file()
            ):
                raise ValueError(
                    f"El archivo '{path}' no existe o no es un archivo válido."
                )
            if mime_type == "text/html":
                self._html = stored_file
                self.FILES_REGISTRY[path] = self._html
            elif mime_type == "text/css":
                self._stylesheets[path] = stored_file
                self.FILES_REGISTRY[path] = self._stylesheets[path]
            else:
                self._assets[path] = stored_file
                self.FILES_REGISTRY[path] = self._assets[path]

        if self._html is not None:
            self._glow_style_sheet = ProjectSource(
                _path=self._html.path.parent / "glow.css",
                _mime_type="text/css",
            )
            self.GENERATED_FILES_REGISTRY[Path("glow.css")] = self._glow_style_sheet

            self.GENERATED_FILES_REGISTRY[Path("before.png")] = ProjectFile(
                _path=g.artifacts_root / "before.png",
                _mime_type="image/png",
            )

            self.GENERATED_FILES_REGISTRY[Path("after.png")] = ProjectFile(
                _path=g.artifacts_root / "after.png",
                _mime_type="image/png",
            )

            self.GENERATED_FILES_REGISTRY[Path("palette_preview.png")] = ProjectFile(
                _path=g.artifacts_root / "palette_preview.png",
                _mime_type="image/png",
            )

        if has_app_context():
            g.project_context = self

    def __len__(self) -> int:
        return len(self.FILES_REGISTRY)

    def __iter__(self):
        return iter(self.FILES_REGISTRY.values())

    @property
    def html(self) -> ProjectSource:
        if self._html is None:
            raise RuntimeError("ProjectContext no tiene HTML registrado.")
        return self._html

    @property
    def stylesheets(self) -> dict[Path, ProjectSource]:
        return self._stylesheets

    @property
    def assets(self) -> dict[Path, ProjectAsset]:
        return self._assets

    @property
    def resources(self) -> dict[str, Resource]:
        return self.RESOURCES_REGISTRY

    @property
    def root(self) -> Path:
        return g.before_root

    @property
    def before_root(self) -> Path:
        return g.before_root

    @property
    def after_root(self) -> Path:
        return g.after_root

    @property
    def artifacts_root(self) -> Path:
        return g.artifacts_root

    @property
    def existing_dirs(self) -> set[str]:
        return self._existing_dirs

    @property
    def glow_style_sheet(self) -> ProjectSource | None:
        return self._glow_style_sheet

    @property
    def failed_files(self) -> list[Path]:
        return self._failed

    @property
    def svgs(self) -> dict[Path, ProjectAsset]:
        return {
            path: file for path, file in self._assets.items() if file.file_type == "svg"
        }

    def dir_exists(self, path: str | Path) -> bool:
        directory = Path(path)
        return bool(list(g.before_root.rglob(f"**/{directory.name}")))

    def get_by_type(self, file_type: str) -> list[Path]:
        value = str(file_type or "").strip().lower()
        if value in _VIDEO_SUFFIXES:
            value = "video"
        if value.startswith("."):
            value = value.removeprefix(".")

        return [
            project_file.absolute_path
            for project_file in self.FILES_REGISTRY.values()
            if project_file.mime_type == value or project_file.file_type == value
        ]

    def copy_area_files(self) -> list[Path]:
        source_root = g.before_root
        target_root = g.after_root
        if not source_root.is_dir():
            return []

        copy_directory_tree(source_root, target_root)
        return sorted(path for path in target_root.rglob("*") if path.is_file())

    def project_file(
        self,
        path: str | Path,
        source: ProjectSource | None = None,
    ) -> ProjectFile | None:
        value = str(path or "").strip()
        match = re.compile(
            r"""^(?:url\(\s*)?(?P<quote>["'])?(?P<value>.*?)(?P=quote)?(?:\s*\))?$""",
            re.IGNORECASE,
        ).fullmatch(value)
        if match is None:
            return None
        value = urlsplit(unquote(match.group("value")))
        if value.scheme in {"http", "https"} and value.hostname not in _LOCAL_HOSTS:
            return None

        if not value.path:
            return None

        reference_path = Path(
            value.path.lstrip("/")
            if value.netloc or value.path.startswith("/")
            else value.path
        )
        candidates: list[Path] = []

        if not value.netloc and not str(value.path).startswith("/"):
            if source is not None:
                candidates.append(source.path.parent / reference_path)
            if self.page_url:
                page_path = Path(urlsplit(self.page_url).path.lstrip("/"))
                candidates.append(page_path.parent / reference_path)

        candidates.append(reference_path)

        for candidate_path in candidates:
            if candidate_path in self.FILES_REGISTRY:
                return self.FILES_REGISTRY[candidate_path]

            if not candidate_path.suffix:
                for registry_path, project_file in self.FILES_REGISTRY.items():
                    if (
                        registry_path.parent == candidate_path.parent
                        and registry_path.stem == candidate_path.name
                    ):
                        return project_file

            candidate_absolute = g.before_root.joinpath(candidate_path)
            for project_file in self.FILES_REGISTRY.values():
                try:
                    if (
                        candidate_absolute.is_file()
                        and candidate_absolute.samefile(project_file.absolute_path)
                    ):
                        return project_file
                except OSError:
                    continue

            if candidate_absolute.parent.is_dir() and not candidate_path.suffix:
                for found in candidate_absolute.parent.glob(f"{candidate_path.name}.*"):
                    for project_file in self.FILES_REGISTRY.values():
                        try:
                            if found.samefile(project_file.absolute_path):
                                return project_file
                        except OSError:
                            continue

        if reference_path.parent == Path("."):
            pattern = (
                reference_path.name
                if reference_path.suffix
                else f"{reference_path.name}.*"
            )
            for found in g.before_root.rglob(pattern):
                for project_file in self.FILES_REGISTRY.values():
                    try:
                        if found.samefile(project_file.absolute_path):
                            return project_file
                    except OSError:
                        continue

    def find_file_by_path(self, path: Path | str) -> ProjectFile | None:
        return self.project_file(path)

    def add_resource(
        self,
        url: str,
        timing: float = 0.0,
        resource_type: str = "unknown",
        load_status: bool = False,
        message: str | None = "",
    ) -> Resource:
        resource = self.RESOURCES_REGISTRY.get(url)
        if resource is None:
            resource = Resource(
                url=url,
                timing=timing or 0.0,
                resource_type=resource_type,
                load_status=load_status,
                message=message,
            )
        else:
            resource.timing = timing or 0.0
            resource.resource_type = resource_type
            resource.load_status = load_status
            resource.message = message

        return resource

    def loaded_svgs(self) -> tuple[ProjectAsset, ...]:
        return tuple(
            asset
            for asset in self._assets.values()
            if asset.file_type == "svg"
            and asset.is_loaded
            and asset.runtime_information is not None
            and bool(asset.runtime_information.element_usages)
        )

    def loaded_css(self) -> tuple[ProjectSource, ...]:
        return tuple(
            source
            for source in self._stylesheets.values()
            if source.file_type == "css"
            and source.is_loaded
            and source.runtime_information is not None
            and source.path.name != "glow.css"
        )

    def failed_resources(self) -> tuple[Resource, ...]:
        return tuple(
            resource
            for resource in self.RESOURCES_REGISTRY.values()
            if resource.load_status is False
        )
