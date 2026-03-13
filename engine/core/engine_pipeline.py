from typing import Any, Dict, Optional, Tuple

import os
from flask import url_for

from app.config import get_session_dirname
from engine.core.pipeline.results_compiler import compile_results
from engine.core.utils.debug_logger import DebugTrace
from engine.file_handling.project_intake_pipeline import process_project_upload
from engine.file_handling.services.artifact_storage_service import (
    create_output_bundle,
    read_text,
)
from engine.file_handling.services.asset_staging_service import copy_project_assets
from engine.file_handling.services.session_cleanup_service import clean_old_sessions
from engine.file_handling.services.session_workspace_service import (
    generate_session_id,
    prepare_static_session_dir,
)
from engine.environmental_assessment.environmental_assessment_pipeline import run_environmental_assessment
from engine.environmental_assessment.models.carbon_footprint_calculator import CarbonFootprintCalculator
from engine.environmental_assessment.utils.environmental_utils import build_default_energy_model
from engine.rendering.models.snapshot_models import SnapshotOptions
from engine.rendering.rendering_pipeline import capture_page_artifacts_pipeline
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
    artifacts = capture_page_artifacts_pipeline(
        html_content=html_content,
        base_path=base_path,
        output_image_path=output_image,
        session_id=session_id,
        include_color_frequencies=True,
        trace=trace,
        label=label,
    )
    return artifacts.color_frequencies or []


def run_engine_pipeline(file) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    trace = DebugTrace(enabled=True)

    session_id = generate_session_id()
    clean_old_sessions(active_session_id=session_id)

    if not file:
        return None, "No se seleccionó ningún archivo."

    trace.add_step("upload.received", {"filename": file.filename})

    project_input = process_project_upload(file, session_id)
    if isinstance(project_input, str):
        trace.add_step("upload.error", {"message": project_input})
        return None, project_input

    html_content = project_input.html_content
    base_path = project_input.normalized_base_path
    html_path = project_input.html_path
    html_filename = project_input.html_filename
    trace.add_step("upload.handled", {"base_path": base_path})

    if not base_path:
        trace.add_step("upload.missing_base_path", {})
        return None, "Para análisis completo (CSS/imagenes), sube un ZIP con el HTML y sus recursos."

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
    original_screenshot_abs = os.path.join(artifacts_dir, "debug_original.png")
    original_artifacts = capture_page_artifacts_pipeline(
        html_content=html_content,
        base_path=base_path,
        output_json_path=original_snapshot_abs,
        output_image=original_screenshot_abs,
        session_id=session_id,
        include_color_frequencies=True,
        trace=trace,
        label="original",
    )
    trace.add_step(
        "analysis.render_snapshot_generated",
        {
            "snapshot_path": original_snapshot_abs,
            "node_count": original_artifacts.snapshot.metadata.get("nodeCount"),
        },
    )

    original_screenshot_name = "debug_original.png"
    color_data = original_artifacts.color_frequencies or []

    footprint = run_environmental_assessment(
        color_data,
        energy_model,
        time_hours=1,
        calculator=calculator,
    )
    total_current = footprint["current_a"]

    trace.add_step(
        "assessment.original",
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

    zip_output_path, zip_filename = create_output_bundle(
        output_dir=output_dir,
        artifacts_dir=artifacts_dir,
        session_id=session_id,
        session_dirname=session_dirname,
    )
    zip_download_url = url_for(
        "main.session_output",
        session_id=session_dirname,
        filename=zip_filename,
    )
    trace.add_step("transformed.zip_created", {"zip_output_path": zip_output_path})

    html_environmental_path = os.path.join(output_dir, html_filename)
    html_environmental_content = read_text(html_environmental_path)
    trace.add_step("transformed.html_loaded", {"html_environmental_path": html_environmental_path})

    environmental_screenshot_abs = os.path.join(artifacts_dir, "debug_environmental.png")
    environmental_screenshot_name = "debug_environmental.png"

    environmental_artifacts = capture_page_artifacts_pipeline(
        html_content=html_environmental_content,
        base_path=output_dir,
        output_image=environmental_screenshot_abs,
        session_id=session_id,
        include_color_frequencies=True,
        trace=trace,
        label="environmental",
    )
    color_data_environmental = environmental_artifacts.color_frequencies or []

    environmental_assessment = run_environmental_assessment(
        color_data_environmental,
        energy_model,
        time_hours=1,
        calculator=calculator,
    )
    environmental_current = environmental_assessment["current_a"]

    trace.add_step(
        "assessment.environmental",
        {
            "environmental_current": environmental_current,
            "environmental_energy_wh": environmental_assessment.get("energy_wh"),
            "environmental_co2eq_per_use": environmental_assessment.get("co2eq_per_use"),
        },
    )

    results_output_path = os.path.join(artifacts_dir, "results.json")
    results = compile_results(
        total_current=total_current,
        footprint=footprint,
        environmental_assessment=environmental_assessment,
        session_id=session_id,
        html_filename=html_filename,
        heuristics_results=heuristics_results,
        trace=trace,
        original_screenshot_rel=original_screenshot_name,
        environmental_screenshot_rel=environmental_screenshot_name,
        session_dirname=session_dirname,
        results_output_path=results_output_path,
    )

    results["download_url"] = zip_download_url
    results["render_snapshot"] = {
        "artifact": "render_snapshot_original.json",
        "node_count": original_artifacts.snapshot.metadata.get("nodeCount"),
    }

    return results, None


def run_pipeline(file) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    return run_engine_pipeline(file)


