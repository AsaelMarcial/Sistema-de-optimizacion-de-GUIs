from __future__ import annotations

from dataclasses import replace

from engine.adapters.browser.render_models import RenderArtifacts, SnapshotOptions
from engine.adapters.browser.snapshot_analyzer import capture_prototype_state_artifacts
from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_capture(session: Session) -> bool:
    return (
        bool(session.input_html_content.strip())
        and bool(session.input_base_path.strip())
        and bool(session.original_screenshot_path.strip())
    )


def _captured_session(session: Session) -> bool:
    return isinstance(session.original_capture, RenderArtifacts)

CONTRACT = StageContract(
    name="capture_original_state",
    requires=(
        context_value("session.runtime.page_builder", PageBuilder),
        context_value("session", Session, validator=_session_ready_for_capture),
    ),
    produces=(
        context_value("session", Session, validator=_captured_session),
        context_value("environmental.inputs.original.raw_pixel_frequencies", list),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    session = context.get("session")
    if context.error or session.original_capture is not None:
        return context

    output_image_path = session.original_screenshot_path
    context.trace.add_stage_event(
        CONTRACT.name,
        "start",
        {
            "base_path": session.input_base_path,
            "output_image": output_image_path,
        },
    )
    artifacts = capture_prototype_state_artifacts(
        html_content=session.input_html_content,
        base_path=session.input_base_path,
        options=SnapshotOptions(include_color_frequencies=True),
        output_image_path=output_image_path,
        page_builder=context.get("session.runtime.page_builder"),
    )
    color_frequencies = list(artifacts.color_frequencies or [])
    context.set("session", replace(session, original_capture=artifacts))
    context.set("environmental.inputs.original.raw_pixel_frequencies", color_frequencies)
    css_overview = artifacts.css_overview or {}

    context.trace.add_step(
        "original_prototype.render_done",
        {
            "screenshot_path": artifacts.screenshot_path,
            "snapshot_node_count": artifacts.snapshot.metadata.get("nodeCount"),
        },
    )
    context.trace.add_step(
        "original_prototype.colors_classified",
        {"distinct_colors": len(color_frequencies)},
    )
    context.trace.add_step(
        "analysis.render_snapshot_generated",
        {
            "snapshot_path": None,
            "node_count": artifacts.snapshot.metadata.get("nodeCount"),
        },
    )
    context.trace.add_step(
        "analysis.css_overview_captured",
        {
            "unused_declaration_count": css_overview.get("unused_declarations", {}).get("count", 0),
            "contrast_issue_count": len(css_overview.get("contrast_issues", [])),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "node_count": artifacts.snapshot.metadata.get("nodeCount"),
            "distinct_colors": len(color_frequencies),
            "css_overview_path": None,
        },
    )
    return context
