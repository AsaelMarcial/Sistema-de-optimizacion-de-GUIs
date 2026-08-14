from __future__ import annotations

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.file_system.file_manager import create_output_bundle
from engine.adapters.source_code_handler.source_code_formatter import (
    export_runtime_sources,
)
from engine.adapters.utils.palette_preview import render_palette_preview
from engine.domain.enums.scope.context_keys import ContextKey as K
from engine.domain.models.color_scheme import ColorScheme
from engine.domain.models.session import Session
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value


def _results_ready(session: Session) -> bool:
    try:
        palette_preview = session.get_path(
            "palette_preview.png",
            "artifacts",
            "png",
        )
        after_html = session.find_by_suffix("after", "html")
        bundle = session.get_path("glow_design.zip", "artifacts", "zip")
        return (
            palette_preview.is_file()
            and palette_preview.stat().st_size > 0
            and len(after_html) == 1
            and bundle.is_file()
            and bundle.stat().st_size > 0
        )
    except (FileNotFoundError, ValueError, OSError):
        return False


CONTRACT = StageContract(
    name="build_results",
    requires=(
        context_value(K.SESSION, Session),
        context_value(K.PAGE_BUILDER, PageBuilder),
        context_value(K.COLOR_SCHEME, ColorScheme),
    ),
    produces=(
        context_value(K.SESSION, Session, validator=_results_ready),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error:
        return context

    session = context.get(K.SESSION)
    page_builder = context.get(K.PAGE_BUILDER)
    color_scheme = context.get(K.COLOR_SCHEME)

    context.trace.add_stage_event(CONTRACT.name, "start")

    palette_preview_path = session.get_path(
        "palette_preview.png",
        "artifacts",
        "png",
    )
    render_palette_preview(
        color_scheme.get_palettes(),
        palette_preview_path,
    )

    copied_after_paths = session.copy_area_files("before", "after")
    before_html = session.find_by_suffix("before", "html")[0]
    before_root = session.get_area_root("before")
    after_root = session.get_area_root("after")

    source_export = export_runtime_sources(
        page_builder=page_builder,
        output_directory=after_root,
        html_filename=before_html.relative_to(before_root).as_posix(),
    )
    session.save_in_after(source_export.html_path)
    for path in source_export.stylesheet_paths.values():
        session.save_in_after(path)

    zip_path, zip_filename = create_output_bundle(
        source_dir=after_root,
        bundle_dir=session.get_area_root("artifacts"),
        bundle_name="glow_design.zip",
    )
    session.save_in_artifacts(session.get_area_root("artifacts") / zip_filename)

    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "palette_preview_path": str(palette_preview_path),
            "copied_after_file_count": len(copied_after_paths),
            "after_html_path": str(source_export.html_path),
            "after_css_paths": [
                str(path)
                for path in source_export.stylesheet_paths.values()
            ],
            "bundle_path": zip_path,
        },
    )
    return context
