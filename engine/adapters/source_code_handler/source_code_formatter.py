from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, Comment, Doctype, Tag
from bs4.formatter import HTMLFormatter

from engine.adapters.browser.page_builder import PageBuilder, _STYLE_MARKER_PREFIX


class UnsortedAttributes(HTMLFormatter):
    def attributes(self, tag):
        for k, v in tag.attrs.items():
            yield k, v


@dataclass(slots=True)
class SourceExportResult:
    html_path: Path
    html_text: str
    stylesheet_paths: dict[str, Path] = field(default_factory=dict)
    stylesheet_texts: dict[str, str] = field(default_factory=dict)
    skipped_stylesheets: list[dict[str, str]] = field(default_factory=list)

def _prepare_html_soup(outer_html: str) -> BeautifulSoup:
    if not outer_html:
        raise ValueError("outer_html no puede estar vacío.")

    soup = BeautifulSoup(outer_html, "html.parser")

    if not any(isinstance(node, Doctype) for node in soup.contents):
        soup.insert(0, Doctype("html"))

    return soup

def _is_marked_style(tag: Tag, marker_value: str) -> bool:
    marker = tag.previous_sibling

    return (
        tag.name is not None
        and tag.name.casefold() == "style"
        and isinstance(marker, Comment)
        and str(marker) == marker_value
    )


def _find_marked_style(
    soup: BeautifulSoup,
    marker_value: str,
) -> Tag | None:
    tag = soup.find(
        lambda candidate: (
            isinstance(candidate, Tag)
            and _is_marked_style(candidate, marker_value)
        )
    )

    return tag if isinstance(tag, Tag) else None


def _remove_marker(
    soup: BeautifulSoup,
    marker_value: str,
) -> None:
    marker = soup.find(
        string=lambda value: (
            isinstance(value, Comment)
            and str(value) == marker_value
        )
    )

    if isinstance(marker, Comment):
        marker.extract()


def update_html(
    html_path: Path,
    soup: BeautifulSoup
) -> str:
    html_text = soup.prettify(formatter=UnsortedAttributes())

    temp_path = html_path.with_name(
        f".{html_path.name}.tmp"
    )

    try:
        html_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temp_path.write_text(
            html_text,
            encoding="utf-8",
        )
        temp_path.replace(html_path)
    except OSError as exc:
        try:
            if temp_path.is_file():
                temp_path.unlink()
        except OSError:
            pass

        raise RuntimeError(
            f"No se pudo escribir HTML runtime en {html_path}: {exc}"
        ) from exc

    return html_text

def update_external_css(
    *,
    stylesheet: Any,
    output_path: Path,
) -> str:
    css_text = stylesheet.current_text

    temp_path = output_path.with_name(
        f".{output_path.name}.tmp"
    )

    try:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        temp_path.write_text(
            css_text,
            encoding="utf-8",
        )
        temp_path.replace(output_path)
    except OSError as exc:
        try:
            if temp_path.is_file():
                temp_path.unlink()
        except OSError:
            pass

        raise RuntimeError(
            f"No se pudo escribir stylesheet runtime en {output_path}: {exc}"
        ) from exc

    print(f"runtime_stylesheet path={output_path.resolve()}")
    return css_text


def _sanitize_path_segment(segment: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", segment)
    return cleaned or "unknown"


def _stylesheet_relative_path(
    *,
    source_url: str,
    document_url: str,
    used_paths: set[str],
) -> Path | None:
    source = urlsplit(source_url)
    document = urlsplit(document_url)

    if source.scheme not in {"http", "https", "file"}:
        return None

    decoded_path = unquote(source.path)
    path_parts = [
        part
        for part in PurePosixPath(decoded_path).parts
        if part not in {"", "/", ".", ".."}
    ]

    if not path_parts:
        path_parts = ["stylesheet.css"]

    if (
        source.scheme in {"http", "https"}
        and source.netloc.casefold() != document.netloc.casefold()
    ):
        path_parts = [
            "external",
            _sanitize_path_segment(source.netloc),
            *path_parts,
        ]

    relative_path = Path(*path_parts)

    if relative_path.suffix.casefold() != ".css":
        relative_path = relative_path.with_suffix(".css")

    path_key = relative_path.as_posix().casefold()
    if path_key not in used_paths:
        used_paths.add(path_key)
        return relative_path

    url_hash = hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:8]
    relative_path = relative_path.with_name(
        f"{relative_path.stem}_{url_hash}{relative_path.suffix}"
    )
    used_paths.add(relative_path.as_posix().casefold())

    return relative_path


def _same_url_path(
    left_url: str,
    right_url: str,
) -> bool:
    left = urlsplit(left_url)
    right = urlsplit(right_url)

    return (
        left.scheme == right.scheme
        and left.netloc == right.netloc
        and unquote(left.path) == unquote(right.path)
    )


def _source_file_exists(
    page_builder: PageBuilder,
    document_url: str,
    source_url: str,
) -> bool:
    source = urlsplit(source_url)
    document = urlsplit(document_url)

    if source.scheme != document.scheme or source.netloc != document.netloc:
        return True

    project_root = page_builder.project_root or page_builder.base_path
    if project_root is None:
        return False

    source_path = [
        part
        for part in PurePosixPath(
            unquote(source.path)
        ).parts
        if part not in {"", "/", ".", ".."}
    ]

    if not source_path:
        return False

    return (project_root / Path(*source_path)).is_file()


def _skip(
    skipped_stylesheets: list[dict[str, str]],
    stylesheet: Any,
    reason: str,
) -> None:
    skipped_stylesheets.append(
        {
            "style_sheet_id": stylesheet.stylesheet_id,
            "source_url": stylesheet.source_url,
            "reason": reason,
        }
    )


def process_stylesheets(
    *,
    page_builder: PageBuilder,
    soup: BeautifulSoup,
    output_root: Path,
    document_url: str,
    html_path: Path
) -> tuple[dict[str, Path], dict[str, str], list[dict[str, str]], str]:
    main_frame_id = page_builder.get_main_frame_id()
    stylesheets = tuple(page_builder.styles.stylesheets.values())
    used_paths: set[str] = set()
    stylesheet_paths: dict[str, Path] = {}
    stylesheet_texts: dict[str, str] = {}
    skipped_stylesheets: list[dict[str, str]] = []

    for stylesheet in stylesheets:
        marker_value = f"{_STYLE_MARKER_PREFIX}{stylesheet.stylesheet_id}"
        style_tag = _find_marked_style(soup, marker_value)

        try:
            if not stylesheet.frame_id:
                _skip(skipped_stylesheets, stylesheet, "Stylesheet sin frame_id.")
                continue

            if stylesheet.frame_id != main_frame_id:
                _skip(skipped_stylesheets, stylesheet, "Stylesheet fuera del documento principal.")
                continue

            if stylesheet.disabled:
                _skip(skipped_stylesheets, stylesheet, "Stylesheet deshabilitada.")
                continue

            if stylesheet.loading_failed:
                _skip(skipped_stylesheets, stylesheet, "La stylesheet no cargó.")
                continue

            if stylesheet.is_constructed:
                _skip(skipped_stylesheets, stylesheet, "Constructed stylesheet no exportable.")
                continue

            if not stylesheet.source_url:
                _skip(skipped_stylesheets, stylesheet, "Stylesheet sin source_url.")
                continue

            match stylesheet.kind:
                case "embedded":
                    if style_tag is None:
                        _skip(skipped_stylesheets, stylesheet, "No se encontró su ubicación en el HTML.")
                        continue

                    if not _same_url_path(stylesheet.source_url, document_url):
                        _skip(skipped_stylesheets, stylesheet, "La stylesheet embebida no pertenece al documento principal.")
                        continue

                    style_tag.clear()
                    style_tag.string = stylesheet.current_text

                    stylesheet_paths[stylesheet.stylesheet_id] = html_path
                    stylesheet_texts[stylesheet.stylesheet_id] = stylesheet.current_text            

                case "external":
                    source_path = PurePosixPath(
                        unquote(urlsplit(stylesheet.source_url).path)
                    )

                    if source_path.suffix.casefold() != ".css":
                        _skip(skipped_stylesheets, stylesheet, "La stylesheet externa no tiene sufijo .css.")
                        continue

                    relative_path = _stylesheet_relative_path(
                        source_url=stylesheet.source_url,
                        document_url=document_url,
                        used_paths=used_paths,
                    )

                    if relative_path is None:
                        _skip(skipped_stylesheets, stylesheet, "No se pudo resolver el path de salida.")
                        continue

                    if not _source_file_exists(
                        page_builder,
                        document_url,
                        stylesheet.source_url,
                    ):
                        _skip(skipped_stylesheets, stylesheet, "No existe el archivo fuente local.")
                        continue

                    output_path = output_root / relative_path
                    css_text = update_external_css(
                        stylesheet=stylesheet,
                        output_path=output_path,
                    )
                    stylesheet_paths[stylesheet.stylesheet_id] = output_path
                    stylesheet_texts[stylesheet.stylesheet_id] = css_text

                case _:
                    _skip(skipped_stylesheets, stylesheet, "Stylesheet no disponible.")

        except Exception as exc:
            _skip(
                skipped_stylesheets,
                stylesheet,
                f"Error procesando stylesheet: {type(exc).__name__}: {exc}",
            )

        finally:
            _remove_marker(soup, marker_value)

    html_text = update_html(
        html_path=html_path,
        soup=soup,
    )

    return stylesheet_paths, stylesheet_texts, skipped_stylesheets, html_text

def export_runtime_sources(
    page_builder: PageBuilder,
    output_directory: str | Path,
    *,
    html_filename: str | None = None,
) -> SourceExportResult:
    page_builder.cache_stylesheets()

    output_root = Path(output_directory).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    html_name = (
        html_filename
        or (
            page_builder.html_path.name
            if page_builder.html_path is not None
            else "index.html"
        )
    )
    html_path = output_root / html_name
    html_path.parent.mkdir(parents=True, exist_ok=True)
    soup = _prepare_html_soup(page_builder.get_outer_html())

    stylesheet_paths, stylesheet_texts, skipped_stylesheets, html_text = process_stylesheets(
        page_builder=page_builder,
        soup=soup,
        output_root=output_root,
        document_url=page_builder.current_url,
        html_path=html_path
    )

    print(f"runtime_html path={html_path.resolve()}")

    return SourceExportResult(
        html_path=html_path,
        html_text=html_text,
        stylesheet_paths=stylesheet_paths,
        stylesheet_texts=stylesheet_texts,
        skipped_stylesheets=skipped_stylesheets,
    )
