from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.browser.render_models import SnapshotOptions
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_page_builder(session: Session) -> bool:
    return bool(session.input_html_content.strip()) and bool(session.input_base_path.strip())

CONTRACT = StageContract(
    name="start_page_builder",
    requires=(
        context_value("session", Session, validator=_session_ready_for_page_builder),
    ),
    produces=(context_value("session.runtime.page_builder", PageBuilder),),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("session.runtime.page_builder"):
        return context

    session = context.get("session")
    context.trace.add_stage_event(CONTRACT.name, "start")
    page_builder = PageBuilder.start(
        session.input_html_content,
        session.input_base_path,
        options=SnapshotOptions(include_color_frequencies=True),
    )
    context.set("session.runtime.page_builder", page_builder)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "base_path": session.input_base_path,
        },
    )
    return context
