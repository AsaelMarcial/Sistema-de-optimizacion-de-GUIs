from __future__ import annotations

from engine.adapters.utils.palette_preview import render_palette_preview
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _palette_preview_ready(session: Session) -> bool:
    try:
        path = session.get_path("palette_preview.png", "artifacts", "png")
        return path.is_file() and path.stat().st_size > 0
    except (FileNotFoundError, ValueError, OSError):
        return False


CONTRACT = StageContract(
    name="build_artifacts",
    requires=(
        context_value(K.SESSION, Session),
        context_value(K.COLOR_SCHEME, ColorScheme),
    ),
    produces=(
        context_value(K.SESSION, Session, validator=_palette_preview_ready),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    session = context.get(K.SESSION)
    color_scheme = context.get(K.COLOR_SCHEME)

    context.trace.add_stage_event(CONTRACT.name, "start")

    output_path = session.get_path("palette_preview.png", "artifacts", "png")
    render_palette_preview(
        color_scheme.get_palettes(),
        output_path,
    )

    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {"palette_preview_path": str(output_path)},
    )
    return context
