from __future__ import annotations

import os
import shutil

from engine.models.pipeline_context import PipelineContext

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


def _copy_project_assets(
    input_dir: str,
    output_dir: str,
    allowed_extensions: tuple[str, ...] = DEFAULT_ASSET_EXTENSIONS,
) -> None:
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if not filename.lower().endswith(allowed_extensions):
                continue

            source_path = os.path.join(root, filename)
            relative_path = os.path.relpath(source_path, input_dir)
            target_path = os.path.join(output_dir, relative_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(source_path, target_path)


def stage_assets(context: PipelineContext) -> None:
    _copy_project_assets(context.base_path or "", context.output_dir or "")
    context.trace.add_step("transformed.resources_prepared", {"output_dir": context.output_dir})
