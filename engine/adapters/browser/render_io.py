from __future__ import annotations

import os
import tempfile

from engine.adapters.utils.io import save_text


TEMP_RENDER_FILE_PREFIX = "__glow_render__-"


def write_temp_render_html(
    html_content: str,
    base_path: str,
    filename: str | None = None,
) -> str:
    if not base_path or not os.path.isdir(base_path):
        raise ValueError("Se requiere un base_path válido para resolver recursos del render.")

    if filename:
        temp_html_path = os.path.join(base_path, filename)
        save_text(temp_html_path, html_content)
        return os.path.abspath(temp_html_path)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".html",
        prefix=TEMP_RENDER_FILE_PREFIX,
        dir=base_path,
        delete=False,
    ) as temp_file:
        temp_file.write(html_content)
        return os.path.abspath(temp_file.name)


def remove_temp_render_html(temp_html_path: str) -> None:
    if temp_html_path and os.path.exists(temp_html_path):
        os.remove(temp_html_path)
