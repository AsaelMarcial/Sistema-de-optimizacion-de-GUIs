from __future__ import annotations

from dataclasses import replace

from engine.adapters.file_system.code_processor import (
    apply_tokens_to_project,
    evaluate_and_apply_heuristics,
    load_transformed_html,
    stage_project_assets,
)
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.session import Session
from engine.domain.models.token import TokenInventoryModel
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_transform(session: Session) -> bool:
    return (
        bool(session.input_html_content.strip())
        and bool(session.input_base_path.strip())
        and bool(session.output_dir.strip())
        and bool(session.output_html_path.strip())
    )


def _transformed_session(session: Session) -> bool:
    return bool(session.output_html_content.strip())

CONTRACT = StageContract(
    name="transform_source_project",
    requires=(
        context_value("session", Session, validator=_session_ready_for_transform),
        context_value("prototype_structure", PrototypeStructure),
        context_value("token.inventory", TokenInventoryModel),
    ),
    produces=(
        context_value("transformation.heuristics", list),
        context_value("transformation.output.html.path", str, validator=lambda value: bool(value.strip())),
        context_value("transformation.output.html.content", str, validator=lambda value: bool(value.strip())),
        context_value("session", Session, validator=_transformed_session),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    session = context.get("session")
    output_dir = session.output_dir
    context.trace.add_stage_event(CONTRACT.name, "start", {"output_dir": output_dir})

    stage_project_assets(
        session.input_base_path,
        session.output_base_path,
    )
    context.trace.add_step("transformed.resources_prepared", {"output_dir": output_dir})

    token_results = apply_tokens_to_project(
        session.input_html_content,
        session.output_html_path,
        session.output_base_path,
        context.get("token.inventory"),
        context.get("prototype_structure"),
    )
    if token_results:
        heuristics_results = token_results
    else:
        heuristics_results = evaluate_and_apply_heuristics(
            session.input_html_content,
            session.output_html_path,
            session.output_base_path,
            None,
        )
    context.set("transformation.heuristics", heuristics_results)
    context.trace.add_step(
        "transformed.heuristics_applied",
        {"heuristics_count": len(heuristics_results)},
    )

    transformed_html_path, transformed_html_content = load_transformed_html(
        session.output_html_path,
    )
    context.set("transformation.output.html.path", transformed_html_path)
    context.set("transformation.output.html.content", transformed_html_content)
    context.set("session", replace(session, output_html_content=transformed_html_content))
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
