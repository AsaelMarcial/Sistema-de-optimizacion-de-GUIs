from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, urlparse, urlunparse

import tinycss2
from bs4 import BeautifulSoup, Tag

from engine.domain.models.asset_records import Asset, AssetRecords, LocalAsset
from engine.domain.models.session import Session

_SRCSET_ATTRIBUTES = {"srcset", "data-srcset"}
_IGNORED_EXTERNAL_SCHEMES = {
    "about",
    "blob",
    "data",
    "javascript",
    "mailto",
    "tel",
}

def extract_reference_candidates(value: str | None, attribute_name: str | None = None) -> list[str]:
    try:
        if not (text := str(value or "").strip()):
            return []

        match str(attribute_name or "").casefold():
            case attr if attr in _SRCSET_ATTRIBUTES:
                return [
                    parts[0] for item in text.split(",") 
                    if (parts := item.split()) and not parts[0].startswith("#")
                ]
            case attr if attr != "":
                c = text.strip("\"'")
                return [c] if c and not c.startswith("#") else []
            case _:
                pending = tinycss2.parse_component_value_list(text, skip_comments=True)
                candidates: set[str] = set()

                while pending:
                    t = pending.pop(0)
                    match (
                        getattr(t, "type", ""),
                        str(getattr(t, "lower_name", getattr(t, "name", ""))).casefold(),
                    ):
                        case ("url", _):
                            candidates.add(str(t.value))
                        case ("function", "url"):
                            candidates.add(tinycss2.serialize(t.arguments).strip().strip("\"'"))
                        case _:
                            if isinstance(nested := getattr(t, "content", getattr(t, "arguments", None)), list):
                                pending.extend(nested)

                return sorted(c for c in candidates if c and not c.startswith("#"))
    except Exception:
        return []

def rewrite_reference_candidates(
    value: str | None,
    new_path: str,
    attribute_name: str | None = None,
) -> str:
    try:
        if not (text := str(value or "").strip()):
            return ""

        match str(attribute_name or "").casefold():
            case attr if attr in _SRCSET_ATTRIBUTES:
                # Reconstruye el srcset inyectando el new_path en cada descriptor
                new_items = []
                for item in text.split(","):
                    if (parts := item.split()) and not parts[0].startswith("#"):
                        # Reemplaza la URL (primer elemento) manteniendo el resto (ej: '2x')
                        parts[0] = new_path
                        new_items.append(" ".join(parts))
                    else:
                        new_items.append(item.strip())
                return ", ".join(new_items)

            case attr if attr != "":
                # Atributo estándar: si no es un ancla, se reemplaza por completo
                return text if text.strip("\"'").startswith("#") else new_path

            case _:
                # Bloque CSS: analizamos, modificamos los tokens y serializamos de vuelta
                tokens = tinycss2.parse_component_value_list(text, skip_comments=True)
                
                # Función auxiliar recursiva para modificar los tokens in-place
                def _modify_tokens(token_list):
                    for t in token_list:
                        match (
                            getattr(t, "type", ""),
                            str(getattr(t, "lower_name", getattr(t, "name", ""))).casefold(),
                        ):
                            case ("url", _):
                                if not str(t.value).startswith("#"):
                                    t.value = new_path
                            case ("function", "url"):
                                # Las funciones url() pueden contener strings o tokens URL
                                # Si no son un ancla, reiniciamos sus argumentos con el nuevo path
                                current_content = tinycss2.serialize(t.arguments).strip().strip("\"'")
                                if not current_content.startswith("#"):
                                    t.arguments = tinycss2.parse_component_value_list(new_path)
                            case _:
                                if isinstance(nested := getattr(t, "content", getattr(t, "arguments", None)), list):
                                    _modify_tokens(nested)

                _modify_tokens(tokens)
                return tinycss2.serialize(tokens)

    except Exception:
        return str(value or "")


def rewrite_local_asset_references(
    html_path: Path,
    session: Session,
    asset_records: AssetRecords,
) -> list[str]:
    html_path = Path(html_path).resolve()
    before_root = session.get_area_root("before").resolve()
    html_base_path = html_path.parent.resolve()
    owner_asset = asset_records.find_asset(html_path)
    if not isinstance(owner_asset, LocalAsset):
        owner_asset = None
    processed_css: set[Path] = set()
    rewritten_values: list[str] = []

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    html_changed = False

    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue

        for attr, value in list(tag.attrs.items()):
            if isinstance(value, str):
                rewritten = _rewrite_value(
                    value,
                    session,
                    asset_records,
                    before_root,
                    html_base_path,
                    html_base_path,
                    owner_asset,
                    attr,
                    processed_css,
                    rewritten_values,
                )
                if rewritten != value:
                    tag[attr] = rewritten
                    html_changed = True
            elif isinstance(value, list):
                original_values = [str(item) for item in value]
                rewritten_attr_values = [
                    _rewrite_value(
                        item,
                        session,
                        asset_records,
                        before_root,
                        html_base_path,
                        html_base_path,
                        owner_asset,
                        attr,
                        processed_css,
                        rewritten_values,
                    )
                    for item in original_values
                ]
                if rewritten_attr_values != original_values:
                    tag[attr] = rewritten_attr_values
                    html_changed = True

        if tag.name and tag.name.casefold() == "style" and tag.string is not None:
            css_text = str(tag.string)
            rewritten = _rewrite_css_urls(
                css_text,
                session,
                asset_records,
                before_root,
                html_base_path,
                html_base_path,
                owner_asset,
                processed_css,
                rewritten_values,
            )
            if rewritten != css_text:
                tag.string.replace_with(rewritten)
                html_changed = True

    if html_changed:
        html_path.write_text(soup.decode(), encoding="utf-8")

    return rewritten_values


def _rewrite_value(
    value: str,
    session: Session,
    asset_records: AssetRecords,
    before_root: Path,
    html_base_path: Path,
    reference_base_path: Path,
    owner_asset: LocalAsset | None,
    attr_name: str = "",
    processed_css: set[Path] | None = None,
    rewritten_values: list[str] | None = None,
) -> str:
    text = value.strip()
    if not text:
        return value

    if "url(" in text.casefold():
        return _rewrite_css_urls(
            value,
            session,
            asset_records,
            before_root,
            html_base_path,
            reference_base_path,
            owner_asset,
            processed_css,
            rewritten_values,
        )

    if attr_name.casefold() in _SRCSET_ATTRIBUTES:
        parts: list[str] = []
        changed = False
        for candidate in value.split(","):
            item = candidate.strip()
            if not item:
                continue
            source, *descriptor = item.split()
            rewritten_source = _rewrite_path(
                source,
                session,
                asset_records,
                before_root,
                html_base_path,
                reference_base_path,
                owner_asset,
                processed_css,
                rewritten_values,
            )
            if rewritten_source != source:
                source = rewritten_source
                changed = True
            parts.append(" ".join((source, *descriptor)))

        return ", ".join(parts) if changed else value

    rewritten_path = _rewrite_path(
        value,
        session,
        asset_records,
        before_root,
        html_base_path,
        reference_base_path,
        owner_asset,
        processed_css,
        rewritten_values,
    )
    if rewritten_path != value:
        return rewritten_path

    if "," not in value:
        return value

    parts: list[str] = []
    changed = False
    for candidate in value.split(","):
        item = candidate.strip()
        if not item:
            continue
        source, *descriptor = item.split()
        rewritten_source = _rewrite_path(
            source,
            session,
            asset_records,
            before_root,
            html_base_path,
            reference_base_path,
            owner_asset,
            processed_css,
            rewritten_values,
        )
        if rewritten_source != source:
            source = rewritten_source
            changed = True
        parts.append(" ".join((source, *descriptor)))

    return ", ".join(parts) if changed else value
def _rewrite_path(
    value: str,
    session: Session,
    asset_records: AssetRecords,
    before_root: Path,
    html_base_path: Path,
    reference_base_path: Path,
    owner_asset: LocalAsset | None = None,
    processed_css: set[Path] | None = None,
    rewritten_values: list[str] | None = None,
) -> str:
    text = value.strip()
    if not text or text.startswith("#"):
        return value

    parsed = urlparse(text)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme.casefold() not in _IGNORED_EXTERNAL_SCHEMES:
            if owner_asset is not None:
                asset_records.add_resource(
                    owner_asset.source,
                    urlunparse(parsed),
                )
            else:
                asset_records.add_asset(urlunparse(parsed), "external")
        return value
    if not parsed.path:
        return value

    path_text = Path(unquote(parsed.path).strip()).as_posix()
    if not path_text:
        return value
    if not (
        path_text.startswith((".", "/", "\\"))
        or "/" in path_text
        or "\\" in path_text
        or bool(Path(path_text).suffix)
    ):
        return value

    root_absolute = path_text.startswith("/")
    path = Path(path_text.lstrip("/") if root_absolute else path_text)
    current_root = before_root if root_absolute else reference_base_path
    current_path = (current_root / path).resolve()

    if current_path.is_file() and current_path.is_relative_to(before_root):
        current_asset = asset_records.find_asset(current_path)
        if current_asset is None:
            current_asset = asset_records.add_asset(current_path, "unknown")
        if owner_asset is not None:
            asset_records.add_resource(owner_asset.source, current_path)
        _rewrite_stylesheet_file_if_needed(
            current_path,
            session,
            asset_records,
            before_root,
            html_base_path,
            current_asset if isinstance(current_asset, LocalAsset) else None,
            processed_css,
            rewritten_values,
        )
        return value

    target_path = session.find_by_full_path("before", path)
    if target_path is None:
        current_root = before_root if root_absolute else reference_base_path
        candidate_path = (current_root / path).resolve()
        unknown_source = (
            Path(candidate_path.relative_to(html_base_path, walk_up=True).as_posix())
            if candidate_path.is_relative_to(before_root)
            else Path(path.as_posix())
        )
        asset = asset_records.add_asset(unknown_source.as_posix(), "unknown")
        if owner_asset is not None:
            asset_records.add_resource(
                owner_asset.source,
                asset.source,
            )
        return value

    target_absolute = (before_root / target_path).resolve()
    if not target_absolute.is_file() or not target_absolute.is_relative_to(before_root):
        asset = asset_records.add_asset(path.as_posix(), "unknown")
        if owner_asset is not None:
            asset_records.add_resource(
                owner_asset.source,
                asset.source,
            )
        return value

    target_asset = asset_records.find_asset(target_absolute)
    if target_asset is None:
        target_asset = asset_records.add_asset(target_absolute, "unknown")
    if owner_asset is not None:
        related_path = asset_records.add_resource(
            owner_asset.source,
            target_absolute,
        )
    else:
        related_path = target_absolute.relative_to(
            reference_base_path,
            walk_up=True,
        ).as_posix()
    _rewrite_stylesheet_file_if_needed(
        target_absolute,
        session,
        asset_records,
        before_root,
        html_base_path,
        target_asset if isinstance(target_asset, LocalAsset) else None,
        processed_css,
        rewritten_values,
    )

    if root_absolute:
        rewritten_path = f"/{target_path.as_posix()}"
    else:
        rewritten_path = str(related_path)

    rewritten = urlunparse(
        parsed._replace(
            path=quote(rewritten_path, safe="/:@"),
        )
    )
    if rewritten_values is not None:
        rewritten_values.append(rewritten)
    return rewritten


def _rewrite_css_urls(
    css_text: str,
    session: Session,
    asset_records: AssetRecords,
    before_root: Path | None = None,
    html_base_path: Path | None = None,
    reference_base_path: Path | None = None,
    owner_asset: LocalAsset | None = None,
    processed_css: set[Path] | None = None,
    rewritten_values: list[str] | None = None,
) -> str:
    if before_root is None or html_base_path is None:
        raise ValueError("before_root y html_base_path son obligatorios.")
    resolved_before_root = Path(before_root)
    resolved_html_base_path = Path(html_base_path)

    tokens = tinycss2.parse_component_value_list(
        css_text,
        skip_comments=False,
    )
    changed = _rewrite_css_url_tokens(
        tokens,
        session,
        asset_records,
        resolved_before_root,
        resolved_html_base_path,
        reference_base_path or resolved_html_base_path,
        owner_asset,
        processed_css,
        rewritten_values,
    )
    return tinycss2.serialize(tokens) if changed else css_text


def _rewrite_css_url_tokens(
    tokens: list[Any],
    session: Session,
    asset_records: AssetRecords,
    before_root: Path,
    html_base_path: Path,
    reference_base_path: Path,
    owner_asset: LocalAsset | None,
    processed_css: set[Path] | None = None,
    rewritten_values: list[str] | None = None,
) -> bool:
    changed = False

    for index, token in enumerate(tokens):
        token_type = getattr(token, "type", "")

        if token_type == "url":
            rewritten = _rewrite_path(
                token.value,
                session,
                asset_records,
                before_root,
                html_base_path,
                reference_base_path,
                owner_asset,
                processed_css,
                rewritten_values,
            )
            if rewritten != token.value:
                token.value = rewritten
                token.representation = f"url({rewritten})"
                changed = True
            continue

        token_name = str(getattr(token, "name", "")).casefold()
        if token_type == "function" and token_name == "url":
            original = tinycss2.serialize(token.arguments).strip().strip("\"'")
            rewritten = _rewrite_path(
                original,
                session,
                asset_records,
                before_root,
                html_base_path,
                reference_base_path,
                owner_asset,
                processed_css,
                rewritten_values,
            )
            if rewritten != original:
                replacement = tinycss2.parse_component_value_list(
                    f"url({rewritten})",
                    skip_comments=False,
                )
                if replacement:
                    tokens[index] = replacement[0]
                    changed = True
            continue

        nested_tokens = (
            getattr(token, "content", None)
            or getattr(token, "arguments", None)
        )
        if isinstance(nested_tokens, list):
            changed = _rewrite_css_url_tokens(
                nested_tokens,
                session,
                asset_records,
                before_root,
                html_base_path,
                reference_base_path,
                owner_asset,
                processed_css,
                rewritten_values,
            ) or changed

    return changed


def _rewrite_stylesheet_file_if_needed(
    css_path: Path,
    session: Session,
    asset_records: AssetRecords,
    before_root: Path,
    html_base_path: Path,
    owner_asset: LocalAsset | None,
    processed_css: set[Path] | None = None,
    rewritten_values: list[str] | None = None,
) -> None:
    css_path = Path(css_path).resolve()
    if css_path.suffix.lower() != ".css":
        return

    if processed_css is None:
        processed_css = set()
    if css_path in processed_css:
        return

    processed_css.add(css_path)
    try:
        css_text = css_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    rewritten = _rewrite_css_urls(
        css_text,
        session,
        asset_records,
        before_root,
        html_base_path,
        css_path.parent,
        owner_asset,
        processed_css,
        rewritten_values,
    )
    if rewritten != css_text:
        css_path.write_text(rewritten, encoding="utf-8")
