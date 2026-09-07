from __future__ import annotations

from pathlib import Path

from flask import g
from prefect.states import Completed, State, raise_state_exception

from engine.adapters.file_system.file_manager import create_output_bundle
from engine.adapters.source_code_handler.source_code_formatter import (
    export_runtime_sources,
)
from engine.adapters.utils.palette_preview import render_palette_preview
from engine.domain.models.project_context import ProjectContext
from engine.pipeline.glow_runtime import (
    glow_flow,
    glow_task,
)


@glow_task
def _results_ready(project_context: ProjectContext | None) -> State:
    if project_context is None:
        raise RuntimeError("No hay ProjectContext para validar resultados.")

    palette_preview = project_context.GENERATED_FILES_REGISTRY[
        Path("palette_preview.png")
    ].absolute_path
    after_html = tuple(g.after_root.rglob("*.html"))
    bundle = g.artifacts_root / "glow_design.zip"
    if (
        palette_preview.is_file()
        and palette_preview.stat().st_size > 0
        and len(after_html) == 1
        and bundle.is_file()
        and bundle.stat().st_size > 0
    ):
        return Completed(message="Resultados listos.")
    raise RuntimeError("Los artefactos de resultados no pasaron validacion.")


@glow_flow
def build_results() -> None:
    palette_preview_path = g.project_context.GENERATED_FILES_REGISTRY[
        Path("palette_preview.png")
    ].absolute_path
    render_palette_preview(
        g.color_scheme.get_palettes(),
        palette_preview_path,
    )

    copied_after_paths = g.project_context.copy_area_files()
    before_html = g.project_context.html.absolute_path

    source_export = export_runtime_sources(
        page_builder=g.page_builder,
        output_directory=g.after_root,
        html_filename=before_html.relative_to(g.before_root).as_posix(),
    )

    zip_path, zip_filename = create_output_bundle(
        source_dir=g.after_root,
        bundle_dir=g.artifacts_root,
        bundle_name="glow_design.zip",
    )

    print(
        {
            "build_results.complete": {
                "palette_preview_path": str(palette_preview_path),
                "copied_after_file_count": len(copied_after_paths),
                "after_html_path": str(source_export.html_path),
                "after_css_paths": [
                    str(path) for path in source_export.stylesheet_paths.values()
                ],
                "bundle_path": zip_path,
            }
        }
    )
    results_ready = _results_ready(g.project_context, return_state=True)
    if (
        results_ready.is_failed()
        or results_ready.is_crashed()
        or results_ready.is_cancelled()
    ):
        raise_state_exception(results_ready)
