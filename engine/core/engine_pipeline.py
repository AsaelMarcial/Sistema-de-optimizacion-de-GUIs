from typing import Any, Dict, Optional, Tuple

import os
import shutil
from flask import url_for

from app.config import get_artifacts_dir, get_output_dir, get_session_dirname
from engine.analysis.utils.html_parser import parse_html
from engine.core.pipeline.results_compiler import compile_results
from engine.core.utils.debug_logger import DebugTrace
from engine.file_handling.file_handling_pipeline import run_file_handling_pipeline
from engine.file_handling.services.project_assets import (
    normalize_base_path_for_single_subdir,
    copiar_recursos,
)
from engine.file_handling.services.session_cleaner import clean_old_sessions
from engine.file_handling.services.session_handler import (
    generate_session_id,
    prepare_static_session_dir,
)
from engine.metrics.sustainable_metrics import CarbonFootprintCalculator, estimate_sustainable_metrics
from engine.metrics.utils.default_energy_model import build_default_energy_model
from engine.rendering.screenshot_analyzer import analyze_screenshot_to_color_data
from engine.transformation.heuristics import evaluar_y_corregir_heuristicas

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

    result = run_file_handling_pipeline(file, session_id)
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

    components = parse_html(html_content)
    trace.add_step("analysis.html_parsed", {"components_type": str(type(components))})

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

    copiar_recursos(base_path, output_dir)
    trace.add_step("opt.resources_prepared", {"output_dir": output_dir})

    resultados_heuristicas = evaluar_y_corregir_heuristicas(
        html_content,
        html_path,
        output_dir,
        session_id,
    )
    trace.add_step(
        "opt.heuristics_applied",
        {
            "heuristics_count": (
                len(resultados_heuristicas) if hasattr(resultados_heuristicas, "__len__") else None
            )
        },
    )

    trace.add_step("opt.resources_copied", {"output_dir": output_dir})

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
    trace.add_step("opt.zip_created", {"zip_output_path": zip_output_path})

    html_optimized_path = os.path.join(output_dir, html_filename)
    with open(html_optimized_path, "r", encoding="utf-8") as f:
        html_optimized_content = f.read()
    trace.add_step("opt.html_loaded", {"html_optimized_path": html_optimized_path})

    optimized_screenshot_abs = os.path.join(artifacts_dir, "debug_optimized.png")
    optimized_screenshot_name = "debug_optimized.png"

    color_data_optimized = analyze_gui_to_color_data(
        html_content=html_optimized_content,
        base_path=output_dir,
        output_image=optimized_screenshot_abs,
        session_id=session_id,
        trace=trace,
        label="optimized",
    )

    optimized_footprint = estimate_sustainable_metrics(
        color_data_optimized,
        energy_model,
        time_hours=1,
        calculator=calculator,
    )
    optimized_current = optimized_footprint["current_a"]

    trace.add_step(
        "metrics.optimized",
        {
            "optimized_current": optimized_current,
            "optimized_energy_wh": optimized_footprint.get("energy_wh"),
            "optimized_co2eq_per_use": optimized_footprint.get("co2eq_per_use"),
        },
    )

    results_output_path = os.path.join(artifacts_dir, "results.json")
    results = compile_results(
        total_current=total_current,
        footprint=footprint,
        optimized_footprint=optimized_footprint,
        session_id=session_id,
        html_filename=html_filename,
        resultados_heuristicas=resultados_heuristicas,
        trace=trace,
        original_screenshot_rel=original_screenshot_name,
        optimized_screenshot_rel=optimized_screenshot_name,
        session_dirname=session_dirname,
        results_output_path=results_output_path,
    )

    results["download_url"] = zip_download_url

    return results, None
