from __future__ import annotations

from engine.models.pipeline_context import PipelineContext
from engine.utils.file_utils import save_json


def compile_final_results(context: PipelineContext) -> None:
    footprint = context.footprint or {}
    environmental_assessment = context.environmental_assessment or {}
    context.results = {
        "total_current": footprint["current_a"],
        "carbon_footprint": footprint["co2eq_per_use"],
        "energy_wh": footprint["energy_wh"],
        "environmental_energy_wh": environmental_assessment["energy_wh"],
        "environmental_co2eq_per_use": environmental_assessment["co2eq_per_use"],
        "session_id": context.session_id or "",
        "session_dirname": context.session_dirname or "",
        "html_name": context.html_filename or "",
        "heuristics": context.heuristics_results or [],
        "debug": context.trace.to_dict() if context.trace else None,
        "debug_screenshots": {
            "original": context.original_screenshot_rel,
            "environmental": context.environmental_screenshot_rel,
        },
    }
    context.results["recommendations"] = (
        context.recommendations.to_dict() if context.recommendations else {"items": [], "summary": None}
    )
    context.results["download_url"] = context.zip_download_url
    context.results["render_snapshot"] = {
        "artifact": "render_snapshot_original.json",
        "node_count": context.original_artifacts.snapshot.metadata.get("nodeCount")
        if context.original_artifacts
        else None,
    }
    if context.results_output_path:
        save_json(context.results_output_path, context.results, indent=4)
