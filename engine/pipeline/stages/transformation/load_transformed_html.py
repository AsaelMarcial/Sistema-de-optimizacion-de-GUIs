from __future__ import annotations

import os

from engine.models.pipeline_context import PipelineContext
from engine.utils.file_utils import read_text


def load_transformed_html(context: PipelineContext) -> None:
    context.transformed_html_path = os.path.join(context.output_dir or "", context.html_filename or "")
    context.transformed_html_content = read_text(context.transformed_html_path)
    context.trace.add_step(
        "transformed.html_loaded",
        {"html_environmental_path": context.transformed_html_path},
    )
