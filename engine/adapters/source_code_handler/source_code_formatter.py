from __future__ import annotations

import hashlib
import posixpath
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import (
    unquote,
    urljoin,
    urlsplit,
    urlunsplit,
)

import tinycss2
from bs4 import BeautifulSoup, Doctype

from engine.adapters.browser.page_builder import PageBuilder


_CSS_DECLARATION_AT_RULES = {
    "font-face",
    "page",
    "counter-style",
    "property",
}
_DUPLICATE_IMPORTANT_RE = re.compile(
    r"(?i)(?:!\s*important\s*){2,}"
)
"""
    EJEMPLO DE USO EM LA STAGE
        output_directory = (
        session.base_path
        / "artifacts"
        / "transformed-source"
    )

    result = export_runtime_sources(
        page_builder=page_builder,
        output_directory=output_directory,
        html_filename="after.html",
    )
"""


@dataclass(slots=True)
class SourceExportResult:
    """
    Resultado completo de la recuperación del código fuente.
    """

    html_path: Path
    html_text: str

    stylesheet_paths: dict[str, Path] = field(
        default_factory=dict
    )

    stylesheet_texts: dict[str, str] = field(
        default_factory=dict
    )

    skipped_stylesheets: list[dict[str, str]] = field(
        default_factory=list
    )


# ---------------------------------------------------------------------------
# CSS FORMATTER
# ---------------------------------------------------------------------------

def _has_parse_errors(
    nodes: list[Any],
) -> bool:
    return any(
        node.type == "error"
        for node in nodes
    )


def clean_css_text(css_text: str) -> str:
    return _DUPLICATE_IMPORTANT_RE.sub(
        " !important",
        css_text,
    )


def _indent_text(
    text: str,
    *,
    level: int,
    indentation: str,
) -> str:
    prefix = indentation * level

    return "\n".join(
        f"{prefix}{line}" if line else ""
        for line in text.splitlines()
    )


def _format_css_declarations(
    content: str | list[Any],
    *,
    level: int,
    indentation: str,
) -> str | None:
    if isinstance(content, str):
        content = clean_css_text(content)

    declarations = tinycss2.parse_declaration_list(
        content,
        skip_comments=False,
        skip_whitespace=True,
    )

    if _has_parse_errors(declarations):
        return None

    prefix = indentation * level
    lines: list[str] = []

    for declaration in declarations:
        if declaration.type == "comment":
            lines.append(
                f"{prefix}/*{declaration.value}*/"
            )
            continue

        if declaration.type == "at-rule":
            at_rule = _format_css_rule(
                declaration,
                level=level,
                indentation=indentation,
            )

            if at_rule:
                lines.append(at_rule)

            continue

        if declaration.type != "declaration":
            continue

        value = tinycss2.serialize(
            declaration.value
        ).strip()

        important = (
            " !important"
            if declaration.important
            else ""
        )

        lines.append(
            f"{prefix}{declaration.name}: "
            f"{value}{important};"
        )

    return "\n".join(lines)


def _format_css_rule(
    rule: Any,
    *,
    level: int,
    indentation: str,
) -> str:
    prefix = indentation * level

    if rule.type == "comment":
        return f"{prefix}/*{rule.value}*/"

    if rule.type == "qualified-rule":
        selector = tinycss2.serialize(
            rule.prelude
        ).strip()

        declarations = _format_css_declarations(
            rule.content,
            level=level + 1,
            indentation=indentation,
        )

        if declarations is None:
            original_content = tinycss2.serialize(
                rule.content
            ).strip()

            return (
                f"{prefix}{selector} {{\n"
                f"{_indent_text(
                    original_content,
                    level=level + 1,
                    indentation=indentation,
                )}\n"
                f"{prefix}}}"
            )

        if not declarations:
            return f"{prefix}{selector} {{}}"

        return (
            f"{prefix}{selector} {{\n"
            f"{declarations}\n"
            f"{prefix}}}"
        )

    if rule.type != "at-rule":
        return ""

    keyword = str(rule.at_keyword)
    lower_keyword = str(rule.lower_at_keyword)

    prelude = tinycss2.serialize(
        rule.prelude
    ).strip()

    header = f"@{keyword}"

    if prelude:
        header += f" {prelude}"

    if rule.content is None:
        return f"{prefix}{header};"

    if lower_keyword in _CSS_DECLARATION_AT_RULES:
        content = _format_css_declarations(
            rule.content,
            level=level + 1,
            indentation=indentation,
        )
    else:
        nested_rules = tinycss2.parse_rule_list(
            rule.content,
            skip_comments=False,
            skip_whitespace=True,
        )

        if _has_parse_errors(nested_rules):
            content = None
        else:
            content = _format_css_rules(
                nested_rules,
                level=level + 1,
                indentation=indentation,
            )

    if content is None:
        original_content = tinycss2.serialize(
            rule.content
        ).strip()

        content = _indent_text(
            original_content,
            level=level + 1,
            indentation=indentation,
        )

    if not content:
        return f"{prefix}{header} {{}}"

    return (
        f"{prefix}{header} {{\n"
        f"{content}\n"
        f"{prefix}}}"
    )


def _format_css_rules(
    rules: list[Any],
    *,
    level: int = 0,
    indentation: str = "    ",
) -> str:
    formatted_rules = [
        _format_css_rule(
            rule,
            level=level,
            indentation=indentation,
        )
        for rule in rules
    ]

    return "\n\n".join(
        rule
        for rule in formatted_rules
        if rule
    )


def format_stylesheet(
    css_text: str,
    *,
    indentation: str = "    ",
) -> str:
    """
    Formatea una stylesheet completa.

    Si tinycss2 encuentra errores de parseo en el nivel principal,
    conserva el contenido original para no perder código.
    """
    css_text = clean_css_text(css_text)

    if not css_text.strip():
        return ""

    rules = tinycss2.parse_stylesheet(
        css_text,
        skip_comments=False,
        skip_whitespace=True,
    )

    if _has_parse_errors(rules):
        return css_text.rstrip() + "\n"

    formatted = _format_css_rules(
        rules,
        indentation=indentation,
    )

    return formatted.rstrip() + "\n"


def format_inline_style(
    css_text: str,
) -> str:
    """
    Formatea el contenido de un atributo style="".
    """
    css_text = clean_css_text(css_text)

    if not css_text.strip():
        return ""

    declarations = tinycss2.parse_declaration_list(
        css_text,
        skip_comments=False,
        skip_whitespace=True,
    )

    if _has_parse_errors(declarations):
        return css_text.strip()

    formatted: list[str] = []

    for declaration in declarations:
        if declaration.type == "comment":
            formatted.append(
                f"/*{declaration.value}*/"
            )
            continue

        if declaration.type != "declaration":
            continue

        value = tinycss2.serialize(
            declaration.value
        ).strip()

        important = (
            " !important"
            if declaration.important
            else ""
        )

        formatted.append(
            f"{declaration.name}: "
            f"{value}{important}"
        )

    if not formatted:
        return ""

    return "; ".join(formatted) + ";"


# ---------------------------------------------------------------------------
# HTML FORMATTER
# ---------------------------------------------------------------------------

def _prepare_html_soup(
    outer_html: str,
) -> BeautifulSoup:
    if not outer_html.strip():
        raise ValueError(
            "outer_html no puede estar vacío."
        )

    soup = BeautifulSoup(
        outer_html,
        "html.parser",
    )

    has_doctype = any(
        isinstance(node, Doctype)
        for node in soup.contents
    )

    if not has_doctype:
        soup.insert(
            0,
            Doctype("html"),
        )

    return soup


def _format_html_style_content(
    soup: BeautifulSoup,
) -> dict[str, str]:
    """
    Sustituye temporalmente los bloques <style> por marcadores.

    BeautifulSoup formatea el HTML y posteriormente se restauran los
    bloques CSS ya procesados por tinycss2.
    """
    style_blocks: dict[str, str] = {}

    for index, style_tag in enumerate(
        soup.find_all("style")
    ):
        style_type = str(
            style_tag.get("type") or "text/css"
        ).strip().casefold()

        if style_type not in {
            "",
            "text/css",
        }:
            continue

        css_text = style_tag.get_text()

        formatted_css = format_stylesheet(
            css_text
        ).rstrip()

        marker = (
            f"__GLOW_STYLE_BLOCK_{index}__"
        )

        style_blocks[marker] = formatted_css

        style_tag.clear()
        style_tag.append(marker)

    for element in soup.find_all(
        attrs={"style": True}
    ):
        style_value = element.get("style")

        if not isinstance(style_value, str):
            continue

        formatted_style = format_inline_style(
            style_value
        )

        if formatted_style:
            element["style"] = formatted_style
        else:
            del element["style"]

    return style_blocks


def _restore_style_blocks(
    html_text: str,
    style_blocks: dict[str, str],
) -> str:
    for marker, css_text in style_blocks.items():
        pattern = re.compile(
            rf"^(?P<indent>[ \t]*)"
            rf"{re.escape(marker)}"
            rf"[ \t]*$",
            re.MULTILINE,
        )

        def replace(
            match: re.Match[str],
        ) -> str:
            indentation = match.group("indent")

            return "\n".join(
                (
                    f"{indentation}{line}"
                    if line
                    else ""
                )
                for line in css_text.splitlines()
            )

        html_text = pattern.sub(
            replace,
            html_text,
        )

    return html_text


def serialize_html(
    soup: BeautifulSoup,
    style_blocks: dict[str, str],
) -> str:
    html_text = soup.prettify(
        formatter="minimal",
    )

    html_text = _restore_style_blocks(
        html_text,
        style_blocks,
    )

    return html_text.rstrip() + "\n"


# ---------------------------------------------------------------------------
# URL AND OUTPUT PATH HELPERS
# ---------------------------------------------------------------------------

def _normalize_url(
    url: str,
) -> str:
    parsed = urlsplit(url)

    return urlunsplit(
        (
            parsed.scheme.casefold(),
            parsed.netloc.casefold(),
            unquote(parsed.path),
            parsed.query,
            "",
        )
    )


def _sanitize_path_segment(
    segment: str,
) -> str:
    cleaned = re.sub(
        r"[^a-zA-Z0-9._-]+",
        "_",
        segment,
    )

    return cleaned or "unknown"


def _stylesheet_relative_path(
    *,
    source_url: str,
    document_url: str,
    used_paths: set[str],
) -> Path | None:
    """
    Convierte sourceURL en una ruta segura dentro del directorio exportado.

    Mismo host:
        http://localhost:8000/css/main.css
        -> css/main.css

    Otro host:
        https://cdn.example.com/styles/main.css
        -> external/cdn.example.com/styles/main.css
    """
    source = urlsplit(source_url)
    document = urlsplit(document_url)

    if source.scheme not in {
        "http",
        "https",
        "file",
    }:
        return None

    decoded_path = unquote(
        source.path
    )

    path_parts = [
        part
        for part in PurePosixPath(
            decoded_path
        ).parts
        if part not in {
            "",
            "/",
            ".",
            "..",
        }
    ]

    if not path_parts:
        path_parts = [
            "stylesheet.css"
        ]

    if (
        source.scheme in {"http", "https"}
        and source.netloc.casefold()
        != document.netloc.casefold()
    ):
        path_parts = [
            "external",
            _sanitize_path_segment(
                source.netloc
            ),
            *path_parts,
        ]

    relative_path = Path(
        *path_parts
    )

    if relative_path.suffix.casefold() != ".css":
        relative_path = relative_path.with_suffix(
            ".css"
        )

    path_key = relative_path.as_posix().casefold()

    if path_key not in used_paths:
        used_paths.add(path_key)
        return relative_path

    url_hash = hashlib.sha1(
        source_url.encode("utf-8")
    ).hexdigest()[:8]

    relative_path = relative_path.with_name(
        f"{relative_path.stem}_{url_hash}"
        f"{relative_path.suffix}"
    )

    used_paths.add(
        relative_path.as_posix().casefold()
    )

    return relative_path


# ---------------------------------------------------------------------------
# STYLESHEET RECOVERY
# ---------------------------------------------------------------------------

def _get_main_document_stylesheets(
    page_builder: PageBuilder,
) -> list[Any]:
    """
    Recupera solamente las stylesheets externas de autor pertenecientes
    al documento principal.

    Se excluyen:

    - stylesheets inline, porque ya están dentro del outerHTML
    - user-agent
    - inspector
    - injected
    - constructed stylesheets
    - hojas cuya carga falló
    """
    main_frame_id = (
        page_builder.get_main_frame_id()
    )

    document = page_builder.styles.documents.get(
        main_frame_id
    )

    if document is None:
        return []

    return [
        stylesheet
        for stylesheet
        in document.stylesheets.values()
        if stylesheet.origin == "regular"
        and bool(stylesheet.source_url)
        and not stylesheet.is_inline
        and not stylesheet.is_constructed
        and not stylesheet.loading_failed
    ]


def _get_embedded_document_stylesheets(
    page_builder: PageBuilder,
) -> list[Any]:
    main_frame_id = page_builder.get_main_frame_id()
    document = page_builder.styles.documents.get(
        main_frame_id
    )

    if document is None:
        return []

    embedded_stylesheets = []

    for stylesheet in document.stylesheets.values():
        if (
            stylesheet.origin == "regular"
            and stylesheet.is_inline
            and not stylesheet.is_constructed
            and not stylesheet.loading_failed
        ):
            embedded_stylesheets.append(stylesheet)

    return embedded_stylesheets


def _stylesheet_has_rules(css_text: str) -> bool:
    rules = tinycss2.parse_stylesheet(
        css_text,
        skip_comments=True,
        skip_whitespace=True,
    )

    if _has_parse_errors(rules):
        return bool(css_text.strip())

    return any(
        rule.type in {
            "qualified-rule",
            "at-rule",
        }
        for rule in rules
    )


def _sync_embedded_stylesheets(
    *,
    soup: BeautifulSoup,
    page_builder: PageBuilder,
) -> None:
    embedded_stylesheets = []

    for stylesheet in _get_embedded_document_stylesheets(
        page_builder
    ):
        try:
            css_text = page_builder.get_stylesheet_text(
                stylesheet.stylesheet_id
            )
        except RuntimeError:
            continue

        css_text = clean_css_text(css_text)

        if not _stylesheet_has_rules(css_text):
            continue

        embedded_stylesheets.append(
            (
                stylesheet,
                css_text,
            )
        )

    style_tags = [
        style_tag
        for style_tag in soup.find_all("style")
        if str(
            style_tag.get("type") or "text/css"
        ).strip().casefold() in {"", "text/css"}
    ]

    for index, (_stylesheet, css_text) in enumerate(
        embedded_stylesheets
    ):
        if index < len(style_tags):
            style_tag = style_tags[index]
        else:
            style_tag = soup.new_tag("style")
            if soup.head is not None:
                soup.head.append(style_tag)
            else:
                soup.append(style_tag)

        style_tag.string = clean_css_text(css_text)


def clean_runtime_css(page_builder: PageBuilder) -> None:
    for document in page_builder.styles.documents.values():
        for stylesheet in document.stylesheets.values():
            try:
                css_text = page_builder.get_stylesheet_text(
                    stylesheet.stylesheet_id
                )
            except RuntimeError:
                continue

            cleaned_css = clean_css_text(css_text)
            if cleaned_css == css_text:
                continue

            page_builder.set_stylesheet_text(
                stylesheet.stylesheet_id,
                cleaned_css,
            )

    page_builder.clean_inline_style_attributes()


def _rewrite_stylesheet_links(
    *,
    soup: BeautifulSoup,
    document_url: str,
    source_to_output: dict[str, Path],
) -> None:
    """
    Actualiza los href de las hojas recuperadas para que el HTML
    exportado apunte a los archivos locales generados.
    """
    for link in soup.find_all(
        "link",
        href=True,
    ):
        rel = link.get("rel") or []

        if isinstance(rel, str):
            rel_values = {
                item.casefold()
                for item in rel.split()
            }
        else:
            rel_values = {
                str(item).casefold()
                for item in rel
            }

        if "stylesheet" not in rel_values:
            continue

        raw_href = str(
            link.get("href") or ""
        )

        absolute_href = urljoin(
            document_url,
            raw_href,
        )

        output_path = source_to_output.get(
            _normalize_url(absolute_href)
        )

        if output_path is None:
            continue

        link["href"] = output_path.as_posix()

        # El contenido fue reformateado, por lo que un hash SRI anterior
        # ya no sería válido.
        link.attrs.pop(
            "integrity",
            None,
        )


# ---------------------------------------------------------------------------
# COMPLETE EXPORT
# ---------------------------------------------------------------------------

def export_runtime_sources(
    page_builder: PageBuilder,
    output_directory: str | Path,
    *,
    html_filename: str | None = None,
) -> SourceExportResult:
    """
    Recupera, formatea y guarda el código actual del documento.

    Exporta:

    - HTML completo.
    - Bloques <style>.
    - Atributos style="".
    - Stylesheets externas pertenecientes al frame principal.
    - Stylesheets importadas registradas dentro del mismo frame.

    Las hojas externas permanecen separadas para conservar la cascada,
    sus rutas relativas y las relaciones mediante @import.
    """
    output_root = Path(
        output_directory
    ).resolve()

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    document_url = (
        page_builder.current_url
    )

    outer_html = (
        page_builder.get_outer_html()
    )

    soup = _prepare_html_soup(
        outer_html
    )

    external_stylesheets = (
        _get_main_document_stylesheets(
            page_builder
        )
    )

    _sync_embedded_stylesheets(
        soup=soup,
        page_builder=page_builder,
    )

    used_paths: set[str] = set()

    source_to_output: dict[
        str,
        Path,
    ] = {}

    stylesheet_paths: dict[
        str,
        Path,
    ] = {}

    stylesheet_texts: dict[
        str,
        str,
    ] = {}

    skipped_stylesheets: list[
        dict[str, str]
    ] = []

    # Primero se recuperan y formatean las hojas externas.
    for stylesheet in external_stylesheets:
        stylesheet_id = (
            stylesheet.stylesheet_id
        )

        source_url = (
            stylesheet.source_url
        )

        relative_path = (
            _stylesheet_relative_path(
                source_url=source_url,
                document_url=document_url,
                used_paths=used_paths,
            )
        )

        if relative_path is None:
            skipped_stylesheets.append(
                {
                    "style_sheet_id":
                        stylesheet_id,
                    "source_url":
                        source_url,
                    "reason":
                        "El esquema de URL no corresponde "
                        "a un archivo exportable.",
                }
            )
            continue

        try:
            css_text = (
                page_builder.get_stylesheet_text(
                    stylesheet_id
                )
            )

        except RuntimeError as exc:
            skipped_stylesheets.append(
                {
                    "style_sheet_id":
                        stylesheet_id,
                    "source_url":
                        source_url,
                    "reason": str(exc),
                }
            )
            continue

        formatted_css = format_stylesheet(
            css_text
        )

        output_path = (
            output_root
            / relative_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            formatted_css,
            encoding="utf-8",
        )
        print(f"runtime_stylesheet path={output_path.resolve()}")

        page_builder.styles.set_stylesheet_text(
            stylesheet_id,
            css_text,
        )

        stylesheet_paths[
            stylesheet_id
        ] = output_path

        stylesheet_texts[
            stylesheet_id
        ] = formatted_css

        source_to_output[
            _normalize_url(source_url)
        ] = relative_path

    # Los links se actualizan antes de serializar el HTML.
    _rewrite_stylesheet_links(
        soup=soup,
        document_url=document_url,
        source_to_output=source_to_output,
    )

    # Después se procesan <style> y style="" dentro del HTML.
    style_blocks = (
        _format_html_style_content(
            soup
        )
    )

    formatted_html = serialize_html(
        soup,
        style_blocks,
    )

    output_html_name = (
        html_filename
        or (
            page_builder.html_path.name
            if page_builder.html_path
            is not None
            else "index.html"
        )
    )

    html_path = (
        output_root
        / output_html_name
    )

    html_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    html_path.write_text(
        formatted_html,
        encoding="utf-8",
    )
    print(f"runtime_html path={html_path.resolve()}")

    return SourceExportResult(
        html_path=html_path,
        html_text=formatted_html,
        stylesheet_paths=stylesheet_paths,
        stylesheet_texts=stylesheet_texts,
        skipped_stylesheets=skipped_stylesheets,
    )
