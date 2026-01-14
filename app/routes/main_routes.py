from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    send_from_directory,
)
import os
import shutil

from app.config import get_output_dir, get_artifacts_dir
from engine.file_handling.services.session_cleaner import clean_old_sessions
from engine.file_handling.services.file_handler import handle_uploaded_file
from engine.file_handling.services.session_handler import create_session
from engine.file_handling.services.project_assets import (
    normalize_base_path_for_single_subdir,
    detectar_html_unico,
    copiar_recursos,
)

from engine.analysis.utils.html_parser import parse_html
from engine.metrics.sustainable_metrics import CarbonFootprintCalculator, estimate_sustainable_metrics
from engine.metrics.utils.default_energy_model import build_default_energy_model
from engine.transformation.heuristics import evaluar_y_corregir_heuristicas
from engine.core.pipeline.gui_pipeline import analyze_gui_to_color_data
from engine.core.pipeline.results_compiler import compile_results
from engine.core.utils.debug_logger import DebugTrace


main = Blueprint("main", __name__)

energy_model = build_default_energy_model()
calculator = CarbonFootprintCalculator()


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/header")
def header():
    return render_template("header.html")


@main.route("/sessions/<session_id>/artifacts/<path:filename>")
def session_artifact(session_id: str, filename: str):
    artifacts_dir = get_artifacts_dir(session_id)
    return send_from_directory(artifacts_dir, filename)


@main.route("/sessions/<session_id>/output/<path:filename>")
def session_output(session_id: str, filename: str):
    output_dir = get_output_dir(session_id)
    return send_from_directory(output_dir, filename)


@main.route("/results", methods=["POST"])
def results():
    clean_old_sessions()

    trace = DebugTrace(enabled=True)

    session = create_session()
    session_id = session["session_id"]

    file = request.files.get("file")
    if not file:
        flash("No se seleccionó ningún archivo.", "error")
        return redirect(url_for("main.index"))

    trace.add_step("upload.received", {"filename": file.filename})

    result = handle_uploaded_file(file, session_id)
    if isinstance(result, str):
        flash(result, "error")
        trace.add_step("upload.error", {"message": result})
        return redirect(url_for("main.index"))

    html_content, base_path, session_id = result
    trace.add_step("upload.handled", {"base_path": base_path})

    if not base_path:
        flash("Para análisis completo (CSS/imagenes), sube un ZIP con el HTML y sus recursos.", "error")
        trace.add_step("upload.missing_base_path", {})
        return redirect(url_for("main.index"))

    base_path = normalize_base_path_for_single_subdir(base_path)
    trace.add_step("project.base_path", {"base_path": base_path})

    html_path = detectar_html_unico(base_path)
    html_filename = os.path.basename(html_path)
    trace.add_step("project.html_detected", {"html_path": html_path, "html_name": html_filename})

    output_dir = get_output_dir(session_id)
    artifacts_dir = get_artifacts_dir(session_id)
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(artifacts_dir, exist_ok=True)
    trace.add_step(
        "session.created",
        {
            "session_id": session_id,
            "output_dir": output_dir,
            "artifacts_dir": artifacts_dir,
        },
    )

    # Parse HTML (componentes) - se mantiene
    components = parse_html(html_content)
    trace.add_step("analysis.html_parsed", {"components_type": str(type(components))})

    # --- GUI ORIGINAL (screenshot) ---
    original_screenshot_abs = os.path.join(artifacts_dir, "debug_original.png")
    original_screenshot_url = url_for(
        "main.session_artifact",
        session_id=session_id,
        filename="debug_original.png",
    )

    color_data = analyze_gui_to_color_data(
        html_content=html_content,
        base_path=base_path,
        output_image=original_screenshot_abs,
        session_id=session_id,
        trace=trace,
        label="original"
    )

    footprint = estimate_sustainable_metrics(
        color_data,
        energy_model,
        time_hours=1,
        calculator=calculator,
    )
    total_current = footprint["current_a"]

    trace.add_step("metrics.original", {
        "total_current": total_current,
        "energy_wh": footprint.get("energy_wh"),
        "co2eq_per_use": footprint.get("co2eq_per_use"),
    })

    # --- OPTIMIZACIÓN ---
    copiar_recursos(base_path, output_dir)
    trace.add_step("opt.resources_prepared", {"output_dir": output_dir})

    resultados_heuristicas = evaluar_y_corregir_heuristicas(html_content, html_path, output_dir, session_id)
    trace.add_step("opt.heuristics_applied", {
        "heuristics_count": len(resultados_heuristicas) if hasattr(resultados_heuristicas, "__len__") else None
    })

    trace.add_step("opt.resources_copied", {"output_dir": output_dir})

    zip_temp_base = os.path.join(artifacts_dir, f"{session_id}_bundle")
    zip_temp_path = f"{zip_temp_base}.zip"
    shutil.make_archive(zip_temp_base, 'zip', output_dir)
    zip_output_path = os.path.join(output_dir, f"{session_id}.zip")
    shutil.move(zip_temp_path, zip_output_path)
    zip_download_url = url_for(
        "main.session_output",
        session_id=session_id,
        filename=f"{session_id}.zip",
    )
    trace.add_step("opt.zip_created", {"zip_output_path": zip_output_path})

    # Leer HTML optimizado final
    html_optimized_path = os.path.join(output_dir, html_filename)
    with open(html_optimized_path, "r", encoding="utf-8") as f:
        html_optimized_content = f.read()
    trace.add_step("opt.html_loaded", {"html_optimized_path": html_optimized_path})

    # --- GUI OPTIMIZADA (screenshot) ---
    optimized_screenshot_abs = os.path.join(artifacts_dir, "debug_optimized.png")
    optimized_screenshot_url = url_for(
        "main.session_artifact",
        session_id=session_id,
        filename="debug_optimized.png",
    )

    # Aqui se analiza la GUI optimizada
    color_data_optimized = analyze_gui_to_color_data(
        html_content=html_optimized_content,
        base_path=output_dir,
        output_image=optimized_screenshot_abs,
        session_id=session_id,
        trace=trace,
        label="optimized"
    )

    optimized_footprint = estimate_sustainable_metrics(
        color_data_optimized,
        energy_model,
        time_hours=1,
        calculator=calculator,
    )
    optimized_current = optimized_footprint["current_a"]

    trace.add_step("metrics.optimized", {
        "optimized_current": optimized_current,
        "optimized_energy_wh": optimized_footprint.get("energy_wh"),
        "optimized_co2eq_per_use": optimized_footprint.get("co2eq_per_use"),
    })

    results_output_path = os.path.join(artifacts_dir, "results.json")
    results = compile_results(
        total_current=total_current,
        footprint=footprint,
        optimized_footprint=optimized_footprint,
        session_id=session_id,
        html_filename=html_filename,
        resultados_heuristicas=resultados_heuristicas,
        trace=trace,
        original_screenshot_rel=original_screenshot_url,
        optimized_screenshot_rel=optimized_screenshot_url,
        results_output_path=results_output_path,
    )

    results["download_url"] = zip_download_url

    return render_template("results.html", results=results)
