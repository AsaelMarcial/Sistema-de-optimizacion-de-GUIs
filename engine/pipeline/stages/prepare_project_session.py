from __future__ import annotations

import os

from engine.adapters.file_system.file_handler import clean_old_sessions, generate_session_id, load_project_input
from engine.domain.models.session import (
    ArtifactGroupModel,
    ProjectStateModel,
    SessionArtifactsModel,
    SessionModel,
)
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="prepare_project_session",
    requires=(
        context_value("session.input.file", allow_none=True),
    ),
    produces=(
        context_value("session.input.project", ProjectStateModel),
        context_value("session.output.project", ProjectStateModel),
        context_value("session.artifacts", SessionArtifactsModel),
        context_value("session.input.base_path", str, validator=lambda value: bool(value.strip())),
        context_value("session.input.html.path", str, validator=lambda value: bool(value.strip())),
        context_value("session.input.html.name", str, validator=lambda value: bool(value.strip())),
        context_value("session.input.html.content", str, validator=lambda value: bool(value.strip())),
        context_value("session.output.id", str, validator=lambda value: bool(value.strip())),
        context_value("session.output.dirname", str, validator=lambda value: bool(value.strip())),
        context_value("session.output.workspace", SessionModel),
        context_value("session.output.paths.output_dir", str, validator=lambda value: bool(value.strip())),
        context_value("session.output.paths.artifacts_dir", str, validator=lambda value: bool(value.strip())),
        context_value(
            "session.output.paths.original.snapshot_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.original.screenshot_png",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.original.css_overview_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.original.contrast_report_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.original.effect_color_report_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.transformed.screenshot_png",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value("session.output.paths.results_json", str, validator=lambda value: bool(value.strip())),
        context_value(
            "session.output.paths.color_scheme_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.tokens_original_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.inventory_graph_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.palette_preview_png",
            str,
            validator=lambda value: bool(value.strip()),
        ),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    context.trace.add_stage_event(CONTRACT.name, "start")
    session_id = generate_session_id()
    clean_old_sessions(active_session_id=session_id)
    context.set("session.output.id", session_id)

    upload = context.get("session.input.file")
    if upload is None:
        context.trace.add_stage_event(CONTRACT.name, "error", {"message": "missing_input_file"})
        return context.set_error("No se seleccionó ningún archivo.")

    context.trace.add_step("upload.received", {"filename": getattr(upload, "filename", None)})
    project_input = load_project_input(upload, session_id)
    if isinstance(project_input, str):
        context.trace.add_step("upload.error", {"message": project_input})
        context.trace.add_stage_event(CONTRACT.name, "error", {"message": project_input})
        return context.set_error(project_input)

    workspace = project_input.workspace
    base_path = project_input.normalized_base_path
    if not base_path:
        context.trace.add_step("upload.missing_base_path", {})
        context.trace.add_stage_event(CONTRACT.name, "error", {"message": "missing_base_path"})
        return context.set_error(
            "Para análisis completo (CSS/imagenes), sube un ZIP con el HTML y sus recursos."
        )

    artifacts_dir = workspace.artifacts_dir
    output_dir = workspace.output_dir
    original_screenshot_name = "debug_original.png"
    transformed_screenshot_name = "debug_environmental.png"
    palette_preview_name = "palette_preview.png"
    original_snapshot_path = os.path.join(artifacts_dir, "render_snapshot_original.json")
    original_screenshot_path = os.path.join(artifacts_dir, original_screenshot_name)
    output_screenshot_path = os.path.join(artifacts_dir, transformed_screenshot_name)
    elements_inventory_path = os.path.join(artifacts_dir, "elements_inventory_original.json")
    styles_inventory_path = os.path.join(artifacts_dir, "styles_inventory_original.json")
    colors_inventory_path = os.path.join(artifacts_dir, "colors_inventory_original.json")
    css_overview_path = os.path.join(artifacts_dir, "css_overview_original.json")
    contrast_report_path = os.path.join(artifacts_dir, "contrast_report_original.json")
    effect_color_report_path = os.path.join(artifacts_dir, "effect_colors_original.json")
    original_pixel_raw_path = os.path.join(artifacts_dir, "pixel_frequencies_original_raw.json")
    original_pixel_display_path = os.path.join(
        artifacts_dir,
        "pixel_frequencies_original_display.json",
    )
    output_pixel_raw_path = os.path.join(artifacts_dir, "pixel_frequencies_output_raw.json")
    results_path = os.path.join(artifacts_dir, "results.json")
    color_scheme_path = os.path.join(artifacts_dir, "color_scheme.json")
    palette_preview_path = os.path.join(artifacts_dir, palette_preview_name)
    tokens_original_path = os.path.join(artifacts_dir, "tokens_original.json")
    inventory_graph_path = os.path.join(artifacts_dir, "inventory_graph.json")
    project_relative_root = os.path.relpath(project_input.normalized_base_path, project_input.base_path)
    if project_relative_root in {".", ""}:
        project_relative_root = ""
    output_project_base_path = (
        os.path.join(output_dir, project_relative_root)
        if project_relative_root
        else output_dir
    )
    relative_html_path = os.path.relpath(project_input.html_path, project_input.normalized_base_path)
    output_html_path = os.path.join(output_project_base_path, relative_html_path)
    input_project = project_input.to_project_state(directory=workspace.input)
    output_project = ProjectStateModel.build(
        directory=workspace.output,
        base_path=output_dir,
        normalized_base_path=output_project_base_path,
        html_path=output_html_path,
        html_name=os.path.basename(output_html_path),
        html_content="",
    )
    artifacts = SessionArtifactsModel.build(
        directory=workspace.artifacts,
        original=ArtifactGroupModel(
            snapshot=original_snapshot_path,
            screenshot=original_screenshot_path,
            pixel_frequencies_raw=original_pixel_raw_path,
            pixel_frequencies_display=original_pixel_display_path,
            elements_inventory=elements_inventory_path,
            styles_inventory=styles_inventory_path,
            colors_inventory=colors_inventory_path,
            extras={
                "css_overview": css_overview_path,
                "contrast_report": contrast_report_path,
                "effect_colors": effect_color_report_path,
            },
        ),
        output=ArtifactGroupModel(
            screenshot=output_screenshot_path,
            pixel_frequencies_raw=output_pixel_raw_path,
        ),
        derived=ArtifactGroupModel(
            color_scheme=color_scheme_path,
            palette_preview=palette_preview_path,
            results=results_path,
            extras={
                "tokens_original": tokens_original_path,
                "inventory_graph": inventory_graph_path,
            },
        ),
    )

    context.set("session.input.project", input_project)
    context.set("session.output.project", output_project)
    context.set("session.artifacts", artifacts)
    context.set("session.input.base_path", base_path)
    context.set("session.input.html.path", project_input.html_path)
    context.set("session.input.html.name", project_input.html_filename)
    context.set("session.input.html.content", project_input.html_content)
    context.set("session.output.dirname", workspace.session_dirname)
    context.set("session.output.workspace", workspace)
    context.set("session.output.paths.output_dir", output_dir)
    context.set("session.output.paths.artifacts_dir", artifacts_dir)
    context.set("session.output.paths.original.snapshot_json", original_snapshot_path)
    context.set("session.output.paths.original.screenshot_png", original_screenshot_path)
    context.set("session.output.paths.original.css_overview_json", css_overview_path)
    context.set("session.output.paths.original.contrast_report_json", contrast_report_path)
    context.set("session.output.paths.original.effect_color_report_json", effect_color_report_path)
    context.set("session.output.paths.original.elements_inventory_json", elements_inventory_path)
    context.set("session.output.paths.original.styles_inventory_json", styles_inventory_path)
    context.set("session.output.paths.original.colors_inventory_json", colors_inventory_path)
    context.set("session.output.paths.original.pixel_frequencies_raw_json", original_pixel_raw_path)
    context.set(
        "session.output.paths.original.pixel_frequencies_display_json",
        original_pixel_display_path,
    )
    context.set("session.output.paths.output.screenshot_png", output_screenshot_path)
    context.set("session.output.paths.output.pixel_frequencies_raw_json", output_pixel_raw_path)
    context.set("session.output.paths.transformed.screenshot_png", output_screenshot_path)
    context.set("session.output.paths.results_json", results_path)
    context.set("session.output.paths.color_scheme_json", color_scheme_path)
    context.set("session.output.paths.palette_preview_png", palette_preview_path)
    context.set("session.output.paths.tokens_original_json", tokens_original_path)
    context.set("session.output.paths.inventory_graph_json", inventory_graph_path)

    context.trace.add_step("upload.handled", {"base_path": base_path})
    context.trace.add_step(
        "project.html_detected",
        {
            "html_path": project_input.html_path,
            "html_name": project_input.html_filename,
        },
    )
    context.trace.add_step(
        "session.created",
        {
            "session_id": session_id,
            "output_dir": output_dir,
            "artifacts_dir": artifacts_dir,
            "session_dirname": workspace.session_dirname,
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "session_id": session_id,
            "html_name": project_input.html_filename,
        },
    )
    return context
