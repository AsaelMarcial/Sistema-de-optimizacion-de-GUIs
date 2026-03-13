from __future__ import annotations

import json
import os
import shutil

from engine.rendering.utils.image_color_utils import json_default_numpy_serializer


TEMP_RENDER_FILE_NAME = "__glow_render__.html"


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def save_json(path: str, data, *, indent: int = 2) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=indent, ensure_ascii=False, default=json_default_numpy_serializer)


def save_text(path: str, content: str) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8") as file:
        file.write(content)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def write_temp_render_html(html_content: str, base_path: str, filename: str = TEMP_RENDER_FILE_NAME) -> str:
    if not base_path or not os.path.isdir(base_path):
        raise ValueError("Se requiere un base_path válido para resolver recursos del render.")

    temp_html_path = os.path.join(base_path, filename)
    save_text(temp_html_path, html_content)
    return os.path.abspath(temp_html_path)


def remove_temp_render_html(temp_html_path: str) -> None:
    if temp_html_path and os.path.exists(temp_html_path):
        os.remove(temp_html_path)


def create_output_bundle(output_dir: str, artifacts_dir: str, session_id: str, session_dirname: str) -> tuple[str, str]:
    bundle_base = os.path.join(artifacts_dir, f"{session_id}_bundle")
    temp_zip_path = f"{bundle_base}.zip"
    shutil.make_archive(bundle_base, "zip", output_dir)
    final_zip_path = os.path.join(output_dir, f"{session_dirname}.zip")
    shutil.move(temp_zip_path, final_zip_path)
    return final_zip_path, os.path.basename(final_zip_path)
