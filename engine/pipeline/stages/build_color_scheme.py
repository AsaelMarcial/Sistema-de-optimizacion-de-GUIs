from __future__ import annotations

from engine.adapters.utils.io import save_json
from engine.adapters.utils.palette_preview import render_palette_preview
from engine.domain.models.palette import ColorSchemeArtifactModel, ColorSchemeInputModel, CorePalettesModel
from engine.domain.utils.color_scheme import build_color_scheme_artifact
from engine.pipeline.context import PipelineContext
from engine.pipeline.stage_contract import StageContract, context_value

CONTRACT = StageContract(
    name="build_color_scheme",
    requires=(
        context_value("scheme.input", ColorSchemeInputModel),
        context_value(
            "session.output.paths.color_scheme_json",
            str,
            validator=lambda value: bool(value.strip()),
        ),
        context_value(
            "session.output.paths.palette_preview_png",
            str,
            validator=lambda value: bool(value.strip()),
        ),
    ),
    produces=(
        context_value("scheme.color_scheme", ColorSchemeArtifactModel),
        context_value("scheme.tonal.palettes", CorePalettesModel),
        context_value("scheme.preview.path", str, validator=lambda value: bool(value.strip())),
    ),
)


def run_stage(context: PipelineContext) -> PipelineContext:
    if context.error or context.has("scheme.color_scheme"):
        return context

    scheme_input = context.get("scheme.input")
    context.trace.add_stage_event(CONTRACT.name, "start")
    color_scheme_model = build_color_scheme_artifact(scheme_input)
    color_scheme = color_scheme_model.to_dict()
    preview_path = context.get("session.output.paths.palette_preview_png")

    save_json(
        context.get("session.output.paths.color_scheme_json"),
        color_scheme,
        indent=4,
    )
    render_palette_preview(color_scheme, preview_path)

    context.set("scheme.color_scheme", color_scheme_model)
    context.set("scheme.tonal.palettes", color_scheme_model.core_palettes)
    context.set("scheme.preview.path", preview_path)
    context.trace.add_step(
        "scheme.built",
        {
            "semantic_color_count": len(color_scheme_model.semantic_colors),
            "chromatic_palette_count": len(color_scheme_model.core_palettes.chromatic_palettes),
        },
    )
    context.trace.add_stage_event(
        CONTRACT.name,
        "complete",
        {
            "semantic_color_count": len(color_scheme_model.semantic_colors),
            "confirmed_pixel_count": color_scheme_model.confirmed_pixel_count,
        },
    )
    return context
