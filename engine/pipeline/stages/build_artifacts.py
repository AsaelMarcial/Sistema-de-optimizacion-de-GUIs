from __future__ import annotations

from engine.adapters.utils.palette_preview import render_palette_preview
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _artifacts_ready(session: Session) -> bool:
    try:
        palette_preview = session.get_path("palette_preview.png", "artifacts", "png")
        glow_css = _theme_css_path(session)
        css_text = glow_css.read_text(encoding="utf-8") if glow_css.is_file() else ""
        return (
            palette_preview.is_file()
            and palette_preview.stat().st_size > 0
            and glow_css.is_file()
            and ":root" in css_text
            and '[data-theme="glow"]' in css_text
            and '[data-theme="original"]' in css_text
        )
    except (FileNotFoundError, ValueError, OSError):
        return False


def _theme_css_path(session: Session):
    html_file = session.find_by_suffix("before", "html")[0]
    return html_file.parent / "glow.css"


CONTRACT = StageContract(
    name="build_artifacts",
    requires=(
        context_value(K.SESSION, Session),
        context_value(K.COLOR_SCHEME, ColorScheme),
    ),
    produces=(
        context_value(K.SESSION, Session, validator=_artifacts_ready),
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
        {
            "palette_preview_path": str(output_path),
        },
    )
    return context
