from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from functools import partialmethod
from pathlib import Path
from typing import BinaryIO, Self
from urllib.parse import unquote, urlsplit, urlunsplit


# ============================================================
# ASSET
# ============================================================

@dataclass(slots=True, kw_only=True, eq=False)
class Asset:
    source: str | Path
    origin: str

    # Network information
    url: str | None = None
    timing: float | None = None
    resource_type: str = "unknown"
    load_status: bool | None = None
    message: str | None = None

    used_by: set[int] = field(
        default_factory=set,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if (
            type(self) is Asset
            and self.origin in {"local", "generated"}
        ):
            raise ValueError(
                "'local' and 'generated' assets must be LocalAsset."
            )

    @property
    def has_network_information(self) -> bool:
        return self.url is not None or self.timing is not None

    @property
    def usages(self) -> Iterator[int]:
        return iter(self.used_by)

    @property
    def type(self) -> str:
        return self.resource_type if not isinstance(self, LocalAsset) else self.file_type

    @property
    def is_used(self) -> bool:
        return bool(self.used_by) and self.load_status is not False

    def add_network_information(
        self,
        url: str,
        timing: float | None,
        resource_type: str = "unknown",
        load_status: bool | None = None,
        message: str | None = None,
    ) -> Self:

        self.url = str(url)
        self.timing = timing
        self.resource_type = resource_type or self.resource_type
        self.load_status = load_status
        self.message = message

        return self

    def add_usage(
        self,
        backend_node_id: int,
    ) -> Self:

        self.used_by.add(backend_node_id)

        return self


# ============================================================
# LOCAL ASSET
# ============================================================

@dataclass(slots=True, kw_only=True, eq=False)
class LocalAsset(Asset):
    path: Path
    file_type: str = "unknown"

    # Si este asset es una versión generada,
    # guarda solamente el source del original.
    original_source: str | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    # Recursos utilizados POR este archivo.
    # Nunca guardamos Asset para evitar referencias.
    _used_resources: set[str] = field(
        default_factory=set,
        repr=False,
        compare=False,
    )

    # Versiones generadas a partir de este archivo.
    _versions: set[str] = field(
        default_factory=set,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        Asset.__post_init__(self)
        self.path = self.path.resolve()

    # --------------------------------------------------------
    # General
    # --------------------------------------------------------

    @property
    def type(self) -> str:
        return (
            self.resource_type
            if self.resource_type != "unknown"
            else self.file_type
        )

    @property
    def is_original(self) -> bool:
        return self.original_source is None

    @property
    def is_modified(self) -> bool:
        return (
            self.original_source is not None
            or bool(self._versions)
        )

    # --------------------------------------------------------
    # Resources used by this LocalAsset
    # --------------------------------------------------------

    @property
    def resources(self) -> Iterator[str]:
        return iter(self._used_resources)

    def resource_reference(
        self,
        related: Asset,
    ) -> str:

        if isinstance(related, LocalAsset):
            return related.path.relative_to(
                self.path.parent,
                walk_up=True,
            ).as_posix()

        return str(related.source)

    def resource(
        self,
        related: Asset,
    ) -> str | None:

        return (
            self.resource_reference(related)
            if str(related.source) in self._used_resources
            else None
        )

    # --------------------------------------------------------
    # Versions
    # --------------------------------------------------------

    @property
    def versions_of(self) -> Iterator[str]:
        return iter(self._versions)

    def version(
        self,
        related: LocalAsset,
    ) -> LocalAsset | None:

        return (
            related
            if str(related.source) in self._versions
            else None
        )


# ============================================================
# ASSET RECORDS
# ============================================================

class AssetRecords:

    def __init__(
        self,
        root: str | Path = ".",
        page_url: str = "",
    ) -> None:

        self._assets: list[Asset] = []

        self.root = root
        self.page_url = page_url

    # ========================================================
    # CONFIGURATION
    # ========================================================

    @property
    def root(self) -> Path:
        return self._root

    @root.setter
    def root(
        self,
        value: str | Path,
    ) -> None:

        self._root = Path(value).resolve()

    @property
    def page_url(self) -> str:
        return self._page_url

    @page_url.setter
    def page_url(
        self,
        value: str,
    ) -> None:

        self._page_url = str(value).strip().rstrip("/")

    # ========================================================
    # ITERATION / FILTERING
    # ========================================================

    def __iter__(self) -> Iterator[Asset]:
        return self.all_assets()

    def __len__(self) -> int:
        return len(self._assets)

    def all_assets(self) -> Iterator[Asset]:
        return iter(self._assets)

    def filter_assets(
        self,
        *conditions: Callable[[Asset], bool],
    ) -> Iterator[Asset]:

        assets = self.all_assets()

        for condition in conditions:
            assets = filter(condition, assets)

        return assets

    local_assets = partialmethod(
        filter_assets,
        lambda asset: isinstance(asset, LocalAsset),
    )

    external_assets = partialmethod(
        filter_assets,
        lambda asset: asset.origin == "external",
    )

    generated_assets = partialmethod(
        filter_assets,
        lambda asset: (
            isinstance(asset, LocalAsset)
            and asset.origin == "generated"
        ),
    )

    modified_assets = partialmethod(
        filter_assets,
        lambda asset: (
            isinstance(asset, LocalAsset)
            and asset.is_modified
        ),
    )

    successful_assets = partialmethod(
        filter_assets,
        lambda asset: asset.load_status is True,
    )

    failed_assets = partialmethod(
        filter_assets,
        lambda asset: asset.load_status is False,
    )

    used_assets = partialmethod(
        filter_assets,
        lambda asset: asset.is_used,
    )

    def assets_by_type(
        self,
        resource_type: str,
        *conditions: Callable[[Asset], bool],
    ) -> Iterator[Asset]:

        return self.filter_assets(
            lambda asset: asset.type == resource_type,
            *conditions,
        )

    # ========================================================
    # FIND
    # ========================================================

    def find_asset(
        self,
        source: str | Path,
    ) -> Asset | None:

        source = self.asset_resource(source)

        for asset in self._assets:
            if str(asset.source) == source:
                return asset

            if asset.url is not None and self.asset_resource(asset.url) == source:
                return asset

        return None

    # ========================================================
    # ADD ASSET
    # ========================================================

    def add_asset(
        self,
        source: str | Path,
        origin: str = "unknown",
    ) -> Asset:

        if (
            asset := self.find_asset(source)
        ) is not None:
            return asset

        self._assets.append(
            Asset(
                source=self.asset_resource(source),
                origin=origin,
            )
        )

        return self._assets[-1]

    # ========================================================
    # ADD LOCAL ASSET
    # ========================================================

    def add_local_asset(
        self,
        path: Path,
        file_type: str = "unknown",
        origin: str = "local",
        original_source: str | None = None,
    ) -> LocalAsset:

        path = (
            path.resolve()
            if path.is_absolute()
            else (self.root / path).resolve()
        )

        match self.find_asset(path):

            case LocalAsset() as asset:
                return asset

            case Asset():
                raise TypeError(
                    f"{path!s} is already registered as Asset."
                )

        self._assets.append(
            LocalAsset(
                source=self.asset_resource(path),
                origin=origin,
                path=path,
                file_type=(
                    path.suffix.removeprefix(".").casefold()
                    if file_type == "unknown" and path.suffix
                    else file_type
                ),
                original_source=original_source,
            )
        )

        return self._assets[-1]

    # ========================================================
    # NETWORK INFORMATION
    # ========================================================

    def add_network_information(
        self,
        url: str,
        timing: float | None,
        resource_type: str = "unknown",
        load_status: bool | None = None,
        message: str | None = None,
        page_url: str | None = None,
    ) -> Asset:

        if page_url is not None:
            self.page_url = page_url

        if (
            asset := self.find_asset(url)
        ) is None:

            match urlsplit(url):

                case resource if (
                    resource.scheme
                    and resource.netloc
                    and not (
                        self.page_url
                        and (page_resource := urlsplit(self.page_url))
                        and resource.scheme == page_resource.scheme
                        and resource.netloc == page_resource.netloc
                    )
                ):
                    asset = self.add_asset(
                        url,
                        origin="external",
                    )

                case _:
                    asset = self.add_asset(
                        url,
                        origin="unknown",
                    )

        return asset.add_network_information(
            url=url,
            timing=timing,
            resource_type=resource_type,
            load_status=load_status,
            message=message,
        )

    # ========================================================
    # ADD RESOURCE USED BY LOCAL ASSET
    # ========================================================

    def add_resource(
        self,
        source: str | Path,
        resource_source: str | Path,
    ) -> str:

        source = self.asset_resource(source)

        asset = next(
            self.local_assets(
                lambda local: (
                    self.asset_resource(local.source)
                    == source
                )
            ),
            None,
        )

        if asset is None:
            raise ValueError(
                f"No LocalAsset found for {source!r}."
            )

        if (
            resource := self.find_asset(resource_source)
        ) is None:

            match urlsplit(str(resource_source)):

                case network if (
                    network.scheme
                    and network.netloc
                    and not (
                        self.page_url
                        and (page_resource := urlsplit(self.page_url))
                        and network.scheme == page_resource.scheme
                        and network.netloc == page_resource.netloc
                    )
                ):
                    resource = self.add_asset(
                        resource_source,
                        origin="external",
                    )

                case _:
                    resource = self.add_asset(
                        resource_source,
                        origin="unknown",
                    )

        asset._used_resources.add(
            str(resource.source)
        )

        return asset.resource(resource)  # type: ignore[return-value]

    # ========================================================
    # ADD VERSION
    # ========================================================

    def add_version(
        self,
        source: str | Path,
        stream: bytes | bytearray | BinaryIO,
    ) -> LocalAsset:

        source = self.asset_resource(source)

        asset = next(
            self.local_assets(
                lambda local: (
                    self.asset_resource(local.source)
                    == source
                )
            ),
            None,
        )

        if asset is None:
            raise ValueError(
                f"No LocalAsset found for {source!r}."
            )

        content = bytes(
            stream
            if isinstance(stream, (bytes, bytearray))
            else stream.read()
        )

        if content == asset.path.read_bytes():
            raise ValueError(
                "The new version has the same content "
                "as the original asset."
            )

        version_suffix = (
            "-glow"
            if not asset._versions
            else f"-glow-{len(asset._versions) + 1}"
        )

        version = self.add_local_asset(
            path=asset.path.with_name(
                f"{asset.path.stem}{version_suffix}{asset.path.suffix}"
            ),
            file_type=asset.file_type,
            origin="generated",
            original_source=str(asset.source),
        )

        version.path.write_bytes(content)

        asset._versions.add(
            str(version.source)
        )

        return asset.version(version) or version

    # ========================================================
    # RESOURCE NORMALIZATION
    # ========================================================

    def asset_resource(
        self,
        asset_resource: str | Path,
    ) -> str:

        value = str(asset_resource).strip()

        match urlsplit(value):

            # ------------------------------------------------
            # URL perteneciente a la página local
            # ------------------------------------------------

            case resource if (
                self.page_url
                and resource.scheme
                and resource.netloc
                and (page_resource := urlsplit(self.page_url))
                and resource.scheme == page_resource.scheme
                and resource.netloc == page_resource.netloc
            ):

                return (
                    self.root
                    / unquote(resource.path).lstrip("/")
                ).resolve().relative_to(
                    self.root,
                    walk_up=True,
                ).as_posix()

            # ------------------------------------------------
            # Path local, relativo o Windows Path
            # ------------------------------------------------

            case resource if (
                not resource.scheme
                or len(resource.scheme) == 1
            ):

                path_value = unquote(resource.path or value)

                return (
                    Path(path_value).resolve()
                    if Path(path_value).is_absolute()
                    else (self.root / path_value).resolve()
                ).relative_to(
                    self.root,
                    walk_up=True,
                ).as_posix()

            # ------------------------------------------------
            # URL
            # ------------------------------------------------

            case resource if (
                resource.scheme
                and (
                    resource.netloc
                    or resource.scheme in {
                        "data",
                        "blob",
                        "file",
                    }
                )
            ):

                return urlunsplit(
                    (
                        resource.scheme.casefold(),
                        resource.netloc.casefold(),
                        resource.path,
                        resource.query,
                        "",
                    )
                )

            case _:
                return value
