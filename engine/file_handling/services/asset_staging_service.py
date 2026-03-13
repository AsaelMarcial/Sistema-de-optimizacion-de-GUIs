from __future__ import annotations

import os
import shutil


DEFAULT_ASSET_EXTENSIONS = (
    ".css",
    ".gif",
    ".html",
    ".jpeg",
    ".jpg",
    ".js",
    ".png",
    ".svg",
    ".webp",
)


def copy_project_assets(
    input_dir: str,
    output_dir: str,
    static_session_dir: str | None = None,
    overwrite_output: bool = True,
    allowed_extensions: tuple[str, ...] = DEFAULT_ASSET_EXTENSIONS,
) -> None:
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if not filename.lower().endswith(allowed_extensions):
                continue

            source_path = os.path.join(root, filename)
            relative_path = os.path.relpath(source_path, input_dir)
            target_path = os.path.join(output_dir, relative_path)

            if not overwrite_output and os.path.exists(target_path):
                continue

            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(source_path, target_path)

    if static_session_dir:
        for root, _, files in os.walk(output_dir):
            for filename in files:
                if not filename.lower().endswith(allowed_extensions):
                    continue

                source_path = os.path.join(root, filename)
                relative_path = os.path.relpath(source_path, output_dir)
                target_path = os.path.join(static_session_dir, relative_path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy2(source_path, target_path)
