from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.browser.render_models import SnapshotOptions
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_page_builder(session: Session) -> bool:
    try:
        candidates = session.find_by_suffix("before", ("html",))
        return len(candidates) == 1 and candidates[0].exists()
    except (FileNotFoundError, RuntimeError, ValueError, OSError):
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
    html_file = session.find_by_suffix("before", ("html",))[0]
    context.trace.add_stage_event(CONTRACT.name, "start")
    page_builder = PageBuilder.new_from_file(
        html_file,
        options=SnapshotOptions(),
        existing=context.get(K.PAGE_BUILDER),
    )
    context.set(K.PAGE_BUILDER, page_builder)
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "html_path": str(html_file),
            "base_path": str(html_file.parent),
        },
    )
    return context
