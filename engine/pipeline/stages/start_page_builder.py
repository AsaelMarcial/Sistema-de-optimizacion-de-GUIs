from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.browser.render_models import SnapshotOptions
from engine.adapters.file_system.file_manager import read_text
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value
from engine.validators.project_uploaded import single_html_file


def _session_ready_for_page_builder(session: Session) -> bool:
    try:
        return session.build_path("before", single_html_file(session.file_paths)).exists()
    except Exception:
        return False

CONTRACT = StageContract(
    name="start_page_builder",
    requires=(
        context_value(K.SESSION, Session, validator=_session_ready_for_page_builder),
    ),
    produces=(context_value(K.PAGE_BUILDER, PageBuilder),),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    session = context.get(K.SESSION)
    html_file = single_html_file(session.file_paths)
    base_path = session.build_path("before", session.project_root_file_path())
    html_content = read_text(session.build_path("before", html_file))
    context.trace.add_stage_event(CONTRACT.name, "start")
    page_builder = PageBuilder.new(
        html_content,
        base_path,
        options=SnapshotOptions(),
        existing=context.get(K.PAGE_BUILDER),
    )
    context.set(K.PAGE_BUILDER, page_builder)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "base_path": str(base_path),
        },
    )
    return context
