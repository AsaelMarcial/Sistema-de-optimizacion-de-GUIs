from __future__ import annotations

import os

from engine.utils.file_utils import save_text


TEMP_RENDER_FILE_NAME = "__glow_render__.html"


def write_temp_render_html(
    html_content: str,
    base_path: str,
    filename: str = TEMP_RENDER_FILE_NAME,
) -> str:
    if not base_path or not os.path.isdir(base_path):
        raise ValueError("Se requiere un base_path válido para resolver recursos del render.")

    temp_html_path = os.path.join(base_path, filename)
    save_text(temp_html_path, html_content)
    return os.path.abspath(temp_html_path)


def remove_temp_render_html(temp_html_path: str) -> None:
    if temp_html_path and os.path.exists(temp_html_path):
        os.remove(temp_html_path)
