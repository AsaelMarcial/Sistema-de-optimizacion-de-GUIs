from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.pipeline.context import PipelineContext
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="close_page_builder",
    requires=(context_value(K.PAGE_BUILDER, PageBuilder),),
    produces=(),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    page_builder = context.get(K.PAGE_BUILDER)
    context.trace.add_stage_event(CONTRACT.name, "start")
    page_builder.close()
    context.delete(K.PAGE_BUILDER)
    context.trace.add_stage_event(CONTRACT.name, "complete")
    return context
