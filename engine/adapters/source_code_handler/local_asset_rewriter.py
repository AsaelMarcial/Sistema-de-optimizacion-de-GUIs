from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from bs4 import BeautifulSoup, Tag

from engine.adapters.source_code_handler.source_code_formatter import UnsortedAttributes

_PATH_ATTRIBUTES = ("href", "src", "poster", "data-href", "data-src")
_SRCSET_ATTRIBUTES = ("srcset", "data-srcset")
_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


@dataclass(slots=True)
class AssetRewriteResult:
    changed: bool
    rewrites: list[dict[str, str]]


def rewrite_local_asset_references(html_path: Path, before_root: Path) -> AssetRewriteResult:
    html_path = Path(html_path).resolve()
    before_root = Path(before_root).resolve()
    base_path = html_path.parent
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    rewrites: list[dict[str, str]] = []

    for tag in soup.find_all(True):
        if not isinstance(tag, Tag):
            continue

        for attr in _PATH_ATTRIBUTES:
            value = tag.get(attr)
            if not isinstance(value, str):
                continue
            rewritten = _rewrite_reference(value, before_root, base_path)
            if rewritten and rewritten != value:
                tag[attr] = rewritten
                rewrites.append({"kind": attr, "from": value, "to": rewritten})

        for attr in _SRCSET_ATTRIBUTES:
            value = tag.get(attr)
            if not isinstance(value, str):
                continue
            rewritten = _rewrite_srcset(value, before_root, base_path)
            if rewritten and rewritten != value:
                tag[attr] = rewritten
                rewrites.append({"kind": attr, "from": value, "to": rewritten})

        style_value = tag.get("style")
        if isinstance(style_value, str):
            rewritten = _rewrite_css_urls(style_value, before_root, base_path)
            if rewritten != style_value:
                tag["style"] = rewritten
                rewrites.append({"kind": "style", "from": style_value, "to": rewritten})

    for style_tag in soup.find_all("style"):
        if not isinstance(style_tag, Tag) or style_tag.string is None:
            continue
        css_text = str(style_tag.string)
        rewritten = _rewrite_css_urls(css_text, before_root, base_path)
        if rewritten != css_text:
            style_tag.string.replace_with(rewritten)
            rewrites.append({"kind": "style-tag", "from": css_text, "to": rewritten})

    if rewrites:
        html_path.write_text(soup.decode(formatter=UnsortedAttributes()), encoding="utf-8")

    return AssetRewriteResult(changed=bool(rewrites), rewrites=rewrites)


def _rewrite_reference(value: str, before_root: Path, base_path: Path) -> str | None:
    local_reference = _local_reference(value)
    if local_reference is None:
        return None

    path_text, root_absolute = local_reference
    current_root = before_root if root_absolute else base_path
    current_path = (current_root / path_text).resolve()
    if current_path.is_file():
        return value

    target_path = _find_existing_asset(path_text, before_root)
    if target_path is None:
        return None

    return target_path.relative_to(base_path, walk_up=True).as_posix()


def _rewrite_srcset(value: str, before_root: Path, base_path: Path) -> str | None:
    parts: list[str] = []
    changed = False
    for candidate in value.split(","):
        item = candidate.strip()
        if not item:
            continue
        source, *descriptor = item.split()
        rewritten_source = _rewrite_reference(source, before_root, base_path)
        if rewritten_source and rewritten_source != source:
            changed = True
            source = rewritten_source
        parts.append(" ".join((source, *descriptor)))

    return ", ".join(parts) if changed else None


def _rewrite_css_urls(css_text: str, before_root: Path, base_path: Path) -> str:
    def replace(match: re.Match[str]) -> str:
        quote = match.group(1)
        value = match.group(2)
        rewritten = _rewrite_reference(value, before_root, base_path)
        if not rewritten:
            return match.group(0)
        return f"url({quote}{rewritten}{quote})"

    return _URL_RE.sub(replace, css_text)


def _local_reference(value: str) -> tuple[str, bool] | None:
    text = value.strip()
    if not text or text.startswith(("#", "data:", "mailto:", "tel:", "javascript:")):
        return None

    parsed = urlsplit(text)
    if parsed.scheme and parsed.scheme not in {"file"}:
        return None
    if parsed.netloc:
        return None

    raw_path = unquote(parsed.path).strip().replace("\\", "/")
    root_absolute = raw_path.startswith("/")
    path_text = raw_path
    if not path_text:
        return None

    parts = [
        part
        for part in PurePosixPath(path_text).parts
        if part not in {"", "/", "."}
    ]
    if not parts or ".." in parts:
        return None

    return Path(*parts).as_posix(), root_absolute


def _find_existing_asset(path_text: str, before_root: Path) -> Path | None:
    relative_path = Path(path_text)
    direct_path = (before_root / relative_path).resolve()
    if direct_path.is_file():
        return direct_path

    matches = [
        path.resolve()
        for path in before_root.rglob(relative_path.name)
        if path.is_file() and path.name == relative_path.name
    ]

    return matches[0] if len(matches) == 1 else None
