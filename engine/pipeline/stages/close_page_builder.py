from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="close_page_builder",
    requires=(context_value("session.page_builder", PageBuilder),),
    produces=(),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    page_builder = context.get("session.page_builder")
    context.trace.add_stage_event(CONTRACT.name, "start")
    page_builder.close()
    context.delete("session.page_builder")
    context.trace.add_stage_event(CONTRACT.name, "complete")
    return context
