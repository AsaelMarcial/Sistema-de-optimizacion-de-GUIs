from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


CONTRACT = StageContract(
    name="close_page_builder",
    requires=(
        context_value(
            K.PAGE_BUILDER,
            PageBuilder,
        ),
    ),
    produces=(),
)


def run_stage(
    context: PipelineContext,
) -> PipelineContext:
    context.trace.add_stage_event(
        CONTRACT.name,
        "start",
    )

    page_builder = context.get(
        K.PAGE_BUILDER
    )

    if page_builder is None:
        context.trace.add_stage_event(
            CONTRACT.name,
            "complete",
            {
                "closed": False,
                "reason": (
                    "No había una instancia de PageBuilder "
                    "registrada en el contexto."
                ),
            },
        )

        return context

    was_open = page_builder.is_open

    try:
        page_builder.close()

    finally:
        # La referencia se elimina incluso si close() produce un error,
        # porque la instancia ya no debe reutilizarse.
        context.delete(
            K.PAGE_BUILDER
        )

    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "closed": was_open,
        },
    )

    return context
