from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
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


def _page_builder_ready(page_builder: PageBuilder) -> bool:
    try:
        return (
            page_builder.is_open
            and page_builder.html_path is not None
            and page_builder.html_path.exists()
            and page_builder.base_path is not None
            and page_builder.base_path.exists()
        )
    except (AttributeError, RuntimeError, OSError):
        return False


CONTRACT = StageContract(
    name="start_page_builder",
    requires=(
        context_value(K.SESSION, Session, validator=_session_ready_for_page_builder),
    ),
    produces=(context_value(K.PAGE_BUILDER, PageBuilder, validator=_page_builder_ready),),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    session = context.get(K.SESSION)
    html_file = session.find_by_suffix("before", ("html",))[0]
    context.trace.add_stage_event(CONTRACT.name, "start")
    existing = context.get(K.PAGE_BUILDER)
    if existing is not None and existing.is_open:
        raise ValueError("Ya existe una instancia activa de PageBuilder.")
    page_builder = PageBuilder()
    page_builder.load_page(html_file)
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
