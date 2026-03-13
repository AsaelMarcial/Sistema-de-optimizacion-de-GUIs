from __future__ import annotations

import os


def normalize_base_path_for_single_subdir(base_path: str) -> str:
    if not base_path or not os.path.isdir(base_path):
        return base_path

    subdirs = [
        dirname
        for dirname in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, dirname))
    ]
    if len(subdirs) == 1:
        return os.path.join(base_path, subdirs[0])

    return base_path


def find_single_html_file(base_path: str) -> str:
    html_files: list[str] = []
    for root, _, files in os.walk(base_path):
        for filename in files:
            if filename.lower().endswith(".html"):
                html_files.append(os.path.join(root, filename))

    if not html_files:
        raise FileNotFoundError("No se encontró ningún archivo .html en el proyecto subido.")

    if len(html_files) > 1:
        raise ValueError(
            f"Se encontraron múltiples archivos .html: {html_files}. El proyecto debe tener solo uno."
        )

    return html_files[0]
