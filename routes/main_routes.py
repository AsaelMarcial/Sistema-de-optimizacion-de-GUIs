from flask import Blueprint, render_template, request, flash, redirect, url_for
import os
import uuid
import shutil

from services.session_cleaner import clean_old_sessions
from services.file_handler import handle_uploaded_file
from services.project_assets import (
    normalize_base_path_for_single_subdir,
    detectar_html_unico,
    copiar_recursos,
)

from utils.html_parser import parse_html
from utils.energy_calculator import EnergyModel, CarbonFootprintCalculator
from utils.heuristic_evaluator import evaluar_y_corregir_heuristicas

from utils.sci_rating import compute_rating_from_sci
from utils.gui_pipeline import analyze_gui_to_color_data
from utils.debug_logger import DebugTrace


main = Blueprint("main", __name__)

#es dummy
energy_model = EnergyModel(
    [1.804551146759771e-07, -3.0220347704227896e-07, 1.4154405902803595e-07],
    [9.412383738420182e-08, -1.5781520809511624e-07, 7.546610037732226e-08],
    [1.3946409007268839e-08, -2.4495186160412765e-08, 1.598790315272048e-08],
    0.120833
)

calculator = CarbonFootprintCalculator()


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/header")
def header():
    return render_template("header.html")


@main.route("/results", methods=["POST"])
def results():
    clean_old_sessions()

    trace = DebugTrace(enabled=True)

    file = request.files.get("file")
    if not file:
        flash("No se seleccionó ningún archivo.", "error")
        return redirect(url_for("main.index"))

    trace.add_step("upload.received", {"filename": file.filename})

    result = handle_uploaded_file(file)
    if isinstance(result, str):
        flash(result, "error")
        trace.add_step("upload.error", {"message": result})
        return redirect(url_for("main.index"))

    html_content, base_path = result
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

    # Crear sesión YA para guardar screenshots (original y optimizada)
    session_id = str(uuid.uuid4())[:8]
    static_session_dir = f"static/corrected/{session_id}"
    os.makedirs(static_session_dir, exist_ok=True)
    trace.add_step("session.created", {"session_id": session_id, "static_session_dir": static_session_dir})

    # Parse HTML (componentes) - se mantiene
    components = parse_html(html_content)
    trace.add_step("analysis.html_parsed", {"components_type": str(type(components))})

    # --- GUI ORIGINAL (screenshot) ---
    original_screenshot_rel = f"corrected/{session_id}/debug_original.png"
    original_screenshot_abs = os.path.join("static", original_screenshot_rel)

    color_data = analyze_gui_to_color_data(
        html_content=html_content,
        base_path=base_path,
        output_image=original_screenshot_abs,
        trace=trace,
        label="original"
    )

    total_current = energy_model.calculate_power(color_data)
    footprint = calculator.calculate(total_current, time_hours=1)
    sci_score = footprint["sci_score"]
    rating = compute_rating_from_sci(sci_score)

    trace.add_step("metrics.original", {
        "total_current": total_current,
        "energy_wh": footprint.get("energy_wh"),
        "co2eq_per_use": footprint.get("co2eq_per_use"),
        "sci_score": sci_score,
        "rating": rating
    })

    # --- OPTIMIZACIÓN ---
    resultados_heuristicas = evaluar_y_corregir_heuristicas(html_content, html_path, base_path, session_id)
    trace.add_step("opt.heuristics_applied", {
        "heuristics_count": len(resultados_heuristicas) if hasattr(resultados_heuristicas, "__len__") else None
    })

    copiar_recursos(base_path, static_session_dir)
    trace.add_step("opt.resources_copied", {})

    zip_output_path = f"static/corrected/{session_id}.zip"
    shutil.make_archive(zip_output_path.replace(".zip", ""), 'zip', static_session_dir)
    trace.add_step("opt.zip_created", {"zip_output_path": zip_output_path})

    # Leer HTML optimizado final
    html_optimized_path = os.path.join(static_session_dir, html_filename)
    with open(html_optimized_path, "r", encoding="utf-8") as f:
        html_optimized_content = f.read()
    trace.add_step("opt.html_loaded", {"html_optimized_path": html_optimized_path})

    # --- GUI OPTIMIZADA (screenshot) ---
    optimized_screenshot_rel = f"corrected/{session_id}/debug_optimized.png"
    optimized_screenshot_abs = os.path.join("static", optimized_screenshot_rel)

    # Aqui se analiza la GUI optimizada
    color_data_optimized = analyze_gui_to_color_data(
        html_content=html_optimized_content,
        base_path=static_session_dir,
        output_image=optimized_screenshot_abs,
        trace=trace,
        label="optimized"
    )

    optimized_current = energy_model.calculate_power(color_data_optimized)
    optimized_footprint = calculator.calculate(optimized_current, time_hours=1)

    trace.add_step("metrics.optimized", {
        "optimized_current": optimized_current,
        "optimized_energy_wh": optimized_footprint.get("energy_wh"),
        "optimized_co2eq_per_use": optimized_footprint.get("co2eq_per_use"),
        "optimized_sci_score": optimized_footprint.get("sci_score"),
    })

    results = {
        # Aqui se llena todo lo de la estimacion del consumo energético y la huella de carbono
        "total_current": total_current,
        "carbon_footprint": footprint["co2eq_per_use"],
        "energy_wh": footprint["energy_wh"],
        "sci_score": footprint["sci_score"],
        "optimized_energy_wh": optimized_footprint["energy_wh"],
        "optimized_co2eq_per_use": optimized_footprint["co2eq_per_use"],
        "optimization_rating": rating,
        
        # Aqui se llena el ID de la sesión
        "session_id": session_id,

        # Aqui se llena el nombre del HTML
        "html_name": html_filename,

        # Aqui se llena el resultado de las heurísticas
        "heuristicas": resultados_heuristicas,

        # debug UI  -- alch no se que hace, ya estaba
        "debug": trace.to_dict(),

        # No es debug, es para mostrar las capturas de pantalla original y optimizada pero ya no le quise cambiar el nombre porque ya estaba funcionando y no quiero romper nada
        "debug_screenshots": {
            "original": original_screenshot_rel,
            "optimized": optimized_screenshot_rel
        },

    }

    return render_template("results.html", results=results)
