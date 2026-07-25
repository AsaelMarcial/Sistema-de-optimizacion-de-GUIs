from __future__ import annotations

from engine.adapters.utils.palette_preview import render_palette_preview
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.session import Session
from engine.domain.models.token import TokenInventory
from engine.domain.utils.css_generator import generate_root_css
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _artifacts_ready(session: Session) -> bool:
    try:
        palette_preview = session.get_path("palette_preview.png", "artifacts", "png")
        glow_css = session.get_path("glow.css", "artifacts", "css")
        return (
            palette_preview.is_file()
            and palette_preview.stat().st_size > 0
            and glow_css.is_file()
            and ":root" in glow_css.read_text(encoding="utf-8")
        )
    except (FileNotFoundError, ValueError, OSError):
        return False


CONTRACT = StageContract(
    name="build_artifacts",
    requires=(
        context_value(K.SESSION, Session),
        context_value(K.COLOR_SCHEME, ColorScheme),
        context_value(K.TOKEN_INVENTORY, TokenInventory),
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
    token_inventory = context.get(K.TOKEN_INVENTORY)

    context.trace.add_stage_event(CONTRACT.name, "start")

    output_path = session.get_path("palette_preview.png", "artifacts", "png")
    render_palette_preview(
        color_scheme.get_palettes(),
        output_path,
    )

    css_path = session.get_path("glow.css", "artifacts", "css")
    css_path.write_text(
        generate_root_css(token_inventory.root_tokens),
        encoding="utf-8",
    )

    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "palette_preview_path": str(output_path),
            "glow_css_path": str(css_path),
        },
    )
    return context
