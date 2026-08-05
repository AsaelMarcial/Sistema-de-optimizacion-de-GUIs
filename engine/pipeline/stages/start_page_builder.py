from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.source_code_handler.local_asset_rewriter import (
    rewrite_local_asset_references,
)
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.session import Session
from engine.domain.models.style import Styles
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _session_ready_for_page_builder(
    session: Session,
) -> bool:
    try:
        html_files = session.find_by_suffix(
            "before",
            "html",
        )

        return (
            len(html_files) == 1
            and html_files[0].is_file()
        )

    except (
        FileNotFoundError,
        RuntimeError,
        ValueError,
        OSError,
    ):
        return False


def _page_builder_ready(
    page_builder: PageBuilder,
) -> bool:
    try:
        document_root = page_builder.document_root

        return (
            page_builder.is_open
            and page_builder.html_path is not None
            and page_builder.html_path.is_file()
            and page_builder.base_path is not None
            and page_builder.base_path.is_dir()
            and document_root is not None
            and bool(document_root)
        )

    except (
        AttributeError,
        RuntimeError,
        OSError,
    ):
        return False


CONTRACT = StageContract(
    name="start_page_builder",
    requires=(
        context_value(
            K.SESSION,
            Session,
            validator=_session_ready_for_page_builder,
        ),
    ),
    produces=(
        context_value(
            K.PAGE_BUILDER,
            PageBuilder,
            validator=_page_builder_ready,
        ),
        context_value(
            K.STYLE,
            Styles,
        ),
    ),
)


def run_stage(
    context: PipelineContext,
) -> PipelineContext:
    if context.error:
        return context

    context.trace.add_stage_event(
        CONTRACT.name,
        "start",
    )

    session = context.get(K.SESSION)

    html_files = session.find_by_suffix(
        "before",
        "html",
    )

    if len(html_files) != 1:
        raise RuntimeError(
            "Se esperaba exactamente un archivo HTML "
            "con el sufijo 'before'."
        )

    html_file = html_files[0]
    before_root = session.get_area_root("before")
    rewrite_result = rewrite_local_asset_references(html_file, before_root)
    if rewrite_result.changed:
        context.trace.add_step(
            "html.asset_paths_rewritten",
            {
                "rewrite_count": len(rewrite_result.rewrites),
                "html_path": str(html_file),
            },
        )

    existing_page_builder = context.get(
        K.PAGE_BUILDER
    )

    if (
        existing_page_builder is not None
        and existing_page_builder.is_open
    ):
        raise RuntimeError(
            "Ya existe una instancia activa de PageBuilder."
        )

    styles = Styles()
    page_builder = PageBuilder(styles=styles)

    try:
        page_builder.load_page(html_file, project_root=before_root)
        failed_stylesheets = [
            stylesheet
            for stylesheet in page_builder.styles.stylesheets.values()
            if stylesheet.loading_failed
        ]
        if failed_stylesheets:
            fallback_result = rewrite_local_asset_references(html_file, before_root)
            if fallback_result.changed:
                context.trace.add_step(
                    "html.asset_paths_rewritten_after_load",
                    {
                        "rewrite_count": len(fallback_result.rewrites),
                        "failed_stylesheets": len(failed_stylesheets),
                    },
                )
                page_builder.load_page(html_file, project_root=before_root)

        context.set(
            K.PAGE_BUILDER,
            page_builder,
        )
        context.set(
            K.STYLE,
            styles,
        )

        stylesheet_count = len(
            page_builder.styles.stylesheets
        )

        context.trace.add_stage_event(
            CONTRACT.name,
            "complete",
            {
                "html_path": str(
                    page_builder.html_path
                ),
                "base_path": str(
                    page_builder.base_path
                ),
                "document_node_id": (
                    page_builder.document_root
                ),
                "stylesheets": stylesheet_count,
            },
        )

        return context

    except Exception as exc:
        try:
            page_builder.close()
        except Exception:
            pass

        raise RuntimeError(
            "PageBuilder startup failed due to an unexpected "
            f"error [{type(exc).__name__}]: {exc}"
        ) from exc
