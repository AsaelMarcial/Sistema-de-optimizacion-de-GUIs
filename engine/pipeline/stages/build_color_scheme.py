from __future__ import annotations

from engine.adapters.utils.palette_preview import render_palette_preview
from engine.adapters.utils.pixel import build_color_histograms
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.element import Element
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_scheme(session: Session) -> bool:
    return bool(session.session_id.strip())


CONTRACT = StageContract(
    name="build_color_scheme",
    requires=(
        context_value(K.DOM_TREE, Element),
        context_value(K.COLOR_SCHEME, ColorScheme),
        context_value(K.SESSION, Session, validator=_session_ready_for_scheme),
    ),
    produces=(
        context_value(K.COLOR_SCHEME, ColorScheme),
        context_value(K.ENVIRONMENTAL_BEFORE_COLOR_HISTOGRAM, list),
        context_value(K.SCHEME_COLOR_HISTOGRAM, list),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has(K.SCHEME_COLOR_HISTOGRAM):
        return context

    session = context.get(K.SESSION)
    color_scheme = context.get(K.COLOR_SCHEME)
    context.trace.add_stage_event(CONTRACT.name, "start")

    color_histograms = build_color_histograms(
        session.get_path("before.png", "artifacts", "png"),
        cluster_distance=6.0,
    )
    for color_index, color in enumerate(color_scheme.get_colors().values(), start=1):
        color_scheme.add_palette(f"Color {color_index}", color)

    context.set(K.COLOR_SCHEME, color_scheme)
    context.set(K.ENVIRONMENTAL_BEFORE_COLOR_HISTOGRAM, color_histograms["environmental"])
    context.set(K.SCHEME_COLOR_HISTOGRAM, color_histograms["scheme"])

    render_palette_preview(
        color_scheme.get_palettes(),
        session.get_path("palette_preview.png", "artifacts", "png"),
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "element_color_count": len(color_scheme.get_colors()),
            "scheme_color_count": len(color_histograms["scheme"]),
            "palette_count": len(color_scheme.get_palettes()),
        },
    )
    return context
