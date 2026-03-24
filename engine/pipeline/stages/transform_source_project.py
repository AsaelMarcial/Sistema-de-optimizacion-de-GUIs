from __future__ import annotations

from engine.adapters.file_system.code_processor import (
    apply_tokens_to_project,
    evaluate_and_apply_heuristics,
    load_transformed_html,
    stage_project_assets,
)
from engine.domain.models.session import ProjectStateModel
from engine.domain.models.inventory_graph import InventoryGraphModel
from engine.domain.models.token import TokenInventoryModel
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="transform_source_project",
    requires=(
        context_value("session.input.html.content", str, validator=lambda value: bool(value.strip())),
        context_value("session.input.html.path", str, validator=lambda value: bool(value.strip())),
        context_value("session.input.html.name", str, validator=lambda value: bool(value.strip())),
        context_value("session.input.base_path", str, validator=lambda value: bool(value.strip())),
        context_value("session.output.paths.output_dir", str, validator=lambda value: bool(value.strip())),
        context_value("session.output.id", str, validator=lambda value: bool(value.strip())),
        context_value("token.inventory", TokenInventoryModel),
        context_value("inventory.graph", InventoryGraphModel),
    ),
    produces=(
        context_value("transformation.heuristics", list),
        context_value("transformation.output.html.path", str, validator=lambda value: bool(value.strip())),
        context_value("transformation.output.html.content", str, validator=lambda value: bool(value.strip())),
        context_value("session.output.project", ProjectStateModel),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    output_dir = context.get("session.output.paths.output_dir", "")
    input_project = context.get("session.input.project")
    output_project = context.get("session.output.project")
    context.trace.add_stage_event(CONTRACT.name, "start", {"output_dir": output_dir})

    stage_project_assets(
        input_project.normalized_base_path,
        output_project.normalized_base_path,
    )
    context.trace.add_step("transformed.resources_prepared", {"output_dir": output_dir})

    token_results = apply_tokens_to_project(
        context.get("session.input.html.content"),
        output_project.html_path,
        output_project.normalized_base_path,
        context.get("token.inventory"),
        context.get("inventory.graph"),
    )
    if token_results:
        heuristics_results = token_results
    else:
        heuristics_results = evaluate_and_apply_heuristics(
            context.get("session.input.html.content"),
            output_project.html_path,
            output_project.normalized_base_path,
            None,
        )
    context.set("transformation.heuristics", heuristics_results)
    context.trace.add_step(
        "transformed.heuristics_applied",
        {"heuristics_count": len(heuristics_results)},
    )

    transformed_html_path, transformed_html_content = load_transformed_html(
        output_project.html_path,
    )
    context.set("transformation.output.html.path", transformed_html_path)
    context.set("transformation.output.html.content", transformed_html_content)
    context.set(
        "session.output.project",
        ProjectStateModel.build(
            directory=output_project.directory,
            upload_path=output_project.upload_path,
            base_path=output_project.base_path,
            normalized_base_path=output_project.normalized_base_path,
            html_path=transformed_html_path,
            html_name=context.get("session.input.html.name"),
            html_content=transformed_html_content,
            download_path=output_project.download_path,
            bundle_path=output_project.bundle_path,
        ),
    )
    context.trace.add_step(
        "transformed.html_loaded",
        {"html_environmental_path": transformed_html_path},
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "heuristics_count": len(heuristics_results),
            "transformed_html_path": transformed_html_path,
        },
    )
    return context
