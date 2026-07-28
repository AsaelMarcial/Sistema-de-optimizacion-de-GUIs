from __future__ import annotations

from engine.adapters.utils.palette_preview import render_palette_preview
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.adapters.browser.page_builder import PageBuilder
from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.element import Element
from engine.domain.models.session import Session
from engine.domain.models.token import TokenInventory
from engine.domain.utils.css_generator import generate_theme_css
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
    html_file = session.find_by_suffix("before", ("html",))[0]
    return html_file.parent / "glow.css"


CONTRACT = StageContract(
    name="build_artifacts",
    requires=(
        context_value(K.SESSION, Session),
        context_value(K.COLOR_SCHEME, ColorScheme),
        context_value(K.TOKEN_INVENTORY, TokenInventory),
        context_value(K.DOM_TREE, Element),
        context_value(K.PAGE_BUILDER, PageBuilder),
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
    root = context.get(K.DOM_TREE)
    page_builder = context.get(K.PAGE_BUILDER)

    context.trace.add_stage_event(CONTRACT.name, "start")

    output_path = session.get_path("palette_preview.png", "artifacts", "png")
    render_palette_preview(
        color_scheme.get_palettes(),
        output_path,
    )

    css_path = _theme_css_path(session)
    token_inventory.generate_property_tokens(root)
    root_css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    css_path.write_text(
        root_css.rstrip()
        + "\n\n"
        + generate_theme_css(token_inventory.property_tokens),
        encoding="utf-8",
    )
    session.save_in_before(css_path)
    data_theme_ready = page_builder.set_data_theme()
    theme_link_ready = page_builder.set_theme_link()

    test = root.property("background-color")
    test_result = None
    if test is not None and root.node_id and hasattr(page_builder, "set_effective_value"):
        test_result = page_builder.set_effective_value(
            root.node_id,
            test.name,
            "var(--Neutral-100)",
        )
        print(str(test_result))

    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "palette_preview_path": str(output_path),
            "glow_css_path": str(css_path),
            "data_theme_ready": data_theme_ready,
            "theme_link_ready": theme_link_ready,
            "test_effective_value": test_result,
        },
    )
    return context
