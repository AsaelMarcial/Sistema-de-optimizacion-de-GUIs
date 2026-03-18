from __future__ import annotations

import os

from engine.adapters.file_system.file_handler import load_project_input
from engine.pipeline.context import PipelineContext


def load_project(context: PipelineContext) -> None:
    if not context.file:
        context.error = "No se seleccionó ningún archivo."
        return

    context.trace.add_step("upload.received", {"filename": context.file.filename})
    project_input = load_project_input(context.file, context.session_id or "")
    if isinstance(project_input, str):
        context.trace.add_step("upload.error", {"message": project_input})
        context.error = project_input
        return

    context.project_input = project_input
    context.workspace = project_input.workspace
    context.base_path = project_input.normalized_base_path
    context.html_path = project_input.html_path
    context.html_filename = project_input.html_filename
    context.html_content = project_input.html_content
    context.output_dir = project_input.workspace.output_dir
    context.artifacts_dir = project_input.workspace.artifacts_dir
    context.session_dirname = project_input.workspace.session_dirname
    context.original_snapshot_path = os.path.join(context.artifacts_dir, "render_snapshot_original.json")
    context.original_screenshot_path = os.path.join(
        context.artifacts_dir,
        context.original_screenshot_rel,
    )
    context.environmental_screenshot_path = os.path.join(
        context.artifacts_dir,
        context.environmental_screenshot_rel,
    )
    context.results_output_path = os.path.join(context.artifacts_dir, "results.json")
    context.palette_analysis_output_path = os.path.join(context.artifacts_dir, "palette_analysis.json")
    context.palette_preview_output_path = os.path.join(
        context.output_dir,
        context.palette_preview_rel,
    )

    context.trace.add_step("upload.handled", {"base_path": context.base_path})
    if not context.base_path:
        context.trace.add_step("upload.missing_base_path", {})
        context.error = "Para análisis completo (CSS/imagenes), sube un ZIP con el HTML y sus recursos."
        return

    context.trace.add_step(
        "project.html_detected",
        {
            "html_path": context.html_path,
            "html_name": context.html_filename,
        },
    )
    context.trace.add_step(
        "session.created",
        {
            "session_id": context.session_id,
            "output_dir": context.output_dir,
            "artifacts_dir": context.artifacts_dir,
            "session_dirname": context.session_dirname,
        },
    )
