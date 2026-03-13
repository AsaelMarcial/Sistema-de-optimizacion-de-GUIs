from typing import Any, Dict, Optional, Tuple

import os
import shutil
from flask import url_for

from app.config import get_session_dirname
from engine.core.pipeline.results_compiler import compile_results
from engine.core.utils.debug_logger import DebugTrace
from engine.rendering.services.render_snapshot_extractor import extract_render_snapshot
from engine.file_handling.file_handling_pipeline import process_file_handling_pipeline
from engine.file_handling.services.project_assets import (
    normalize_base_path_for_single_subdir,
    copy_project_assets,
)
from engine.file_handling.services.session_cleaner import clean_old_sessions
from engine.file_handling.services.session_handler import (
    generate_session_id,
    prepare_static_session_dir,
)
from engine.metrics.sustainable_metrics import (
    CarbonFootprintCalculator,
    estimate_sustainable_metrics,
)
from engine.metrics.utils.default_energy_model import build_default_energy_model
from engine.rendering.screenshot_analyzer import analyze_screenshot_to_color_data
from engine.transformation.transformations_pipeline import evaluate_and_apply_heuristics

energy_model = build_default_energy_model()
calculator = CarbonFootprintCalculator()


def analyze_gui_to_color_data(
    html_content: str,
    base_path: str,
    output_image: Optional[str] = None,
    session_id: Optional[str] = None,
    trace: Optional[Any] = None,
    label: str = "gui",
) -> Dict[str, Any]:
    """
    Pipeline: render (con base_path como raíz de recursos) -> pixels -> color frequencies.
    """
    return analyze_screenshot_to_color_data(
        html_content=html_content,
        base_path=base_path,
        output_image=output_image,
        session_id=session_id,
        trace=trace,
        label=label,
    )


def run_engine_pipeline(file) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    trace = DebugTrace(enabled=True)

    session_id = generate_session_id()
    clean_old_sessions(active_session_id=session_id)

    if not file:
        return None, "No se seleccionó ningún archivo."

    trace.add_step("upload.received", {"filename": file.filename})

    result = process_file_handling_pipeline(file, session_id)
    if isinstance(result, str):
        trace.add_step("upload.error", {"message": result})
        return None, result

    html_content, base_path, html_path, html_filename = result
    trace.add_step("upload.handled", {"base_path": base_path})

    if not base_path:
        trace.add_step("upload.missing_base_path", {})
        return None, "Para análisis completo (CSS/imagenes), sube un ZIP con el HTML y sus recursos."

    base_path = normalize_base_path_for_single_subdir(base_path)
    trace.add_step("project.base_path", {"base_path": base_path})

    trace.add_step("project.html_detected", {"html_path": html_path, "html_name": html_filename})

    static_dirs = prepare_static_session_dir(session_id)
    output_dir = static_dirs["output_dir"]
    artifacts_dir = static_dirs["artifacts_dir"]
    session_dirname = get_session_dirname(session_id)
    trace.add_step(
        "session.created",
        {
            "session_id": session_id,
            "output_dir": output_dir,
            "artifacts_dir": artifacts_dir,
            "session_dirname": session_dirname,
        },
    )

    original_snapshot_abs = os.path.join(artifacts_dir, "render_snapshot_original.json")
    snapshot_data = extract_render_snapshot(
        html_content=html_content,
        base_path=base_path,
        output_json_path=original_snapshot_abs,
    )
    trace.add_step(
        "analysis.render_snapshot_generated",
        {
            "snapshot_path": original_snapshot_abs,
            "node_count": snapshot_data.get("metadata", {}).get("nodeCount"),
        },
    )

    original_screenshot_abs = os.path.join(artifacts_dir, "debug_original.png")
    original_screenshot_name = "debug_original.png"

    color_data = analyze_gui_to_color_data(
        html_content=html_content,
        base_path=base_path,
        output_image=original_screenshot_abs,
        session_id=session_id,
        trace=trace,
        label="original",
    )

    footprint = estimate_sustainable_metrics(
        color_data,
        energy_model,
        time_hours=1,
        calculator=calculator,
    )
    total_current = footprint["current_a"]

    trace.add_step(
        "metrics.original",
        {
            "total_current": total_current,
            "energy_wh": footprint.get("energy_wh"),
            "co2eq_per_use": footprint.get("co2eq_per_use"),
        },
    )

    copy_project_assets(base_path, output_dir)
    trace.add_step("transformed.resources_prepared", {"output_dir": output_dir})

    heuristics_results = evaluate_and_apply_heuristics(
        html_content,
        html_path,
        output_dir,
        session_id,
    )
    trace.add_step(
        "transformed.heuristics_applied",
        {
            "heuristics_count": (
                len(heuristics_results) if hasattr(heuristics_results, "__len__") else None
            )
        },
    )

    trace.add_step("transformed.resources_copied", {"output_dir": output_dir})

    zip_filename = f"{session_dirname}.zip"
    zip_temp_base = os.path.join(artifacts_dir, f"{session_id}_bundle")
    zip_temp_path = f"{zip_temp_base}.zip"
    shutil.make_archive(zip_temp_base, "zip", output_dir)
    zip_output_path = os.path.join(output_dir, zip_filename)
    shutil.move(zip_temp_path, zip_output_path)
    zip_download_url = url_for(
        "main.session_output",
        session_id=session_dirname,
        filename=zip_filename,
    )
    trace.add_step("transformed.zip_created", {"zip_output_path": zip_output_path})

    html_sustainable_path = os.path.join(output_dir, html_filename)
    with open(html_sustainable_path, "r", encoding="utf-8") as f:
        html_sustainable_content = f.read()
    trace.add_step("transformed.html_loaded", {"html_sustainable_path": html_sustainable_path})

    sustainable_screenshot_abs = os.path.join(artifacts_dir, "debug_sustainable.png")
    sustainable_screenshot_name = "debug_sustainable.png"

    color_data_sustainable = analyze_gui_to_color_data(
        html_content=html_sustainable_content,
        base_path=output_dir,
        output_image=sustainable_screenshot_abs,
        session_id=session_id,
        trace=trace,
        label="sustainable",
    )

    sustainable_footprint = estimate_sustainable_metrics(
        color_data_sustainable,
        energy_model,
        time_hours=1,
        calculator=calculator,
    )
    sustainable_current = sustainable_footprint["current_a"]

    trace.add_step(
        "metrics.sustainable",
        {
            "sustainable_current": sustainable_current,
            "sustainable_energy_wh": sustainable_footprint.get("energy_wh"),
            "sustainable_co2eq_per_use": sustainable_footprint.get("co2eq_per_use"),
        },
    )

    results_output_path = os.path.join(artifacts_dir, "results.json")
    results = compile_results(
        total_current=total_current,
        footprint=footprint,
        sustainable_footprint=sustainable_footprint,
        session_id=session_id,
        html_filename=html_filename,
        heuristics_results=heuristics_results,
        trace=trace,
        original_screenshot_rel=original_screenshot_name,
        sustainable_screenshot_rel=sustainable_screenshot_name,
        session_dirname=session_dirname,
        results_output_path=results_output_path,
    )

    results["download_url"] = zip_download_url
    results["render_snapshot"] = {
        "artifact": "render_snapshot_original.json",
        "node_count": snapshot_data.get("metadata", {}).get("nodeCount"),
    }

    return results, None


def run_pipeline(file) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    return run_engine_pipeline(file)


