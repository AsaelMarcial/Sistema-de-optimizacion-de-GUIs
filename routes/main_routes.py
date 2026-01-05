from flask import Blueprint, render_template, request, flash, redirect, url_for
from services.session_cleaner import clean_old_sessions
from utils.html_parser import parse_html
from utils.gui_analyzer import analyze_gui
from utils.pixel_processor import extract_pixels
from utils.color_classifier import classify_colors
from utils.energy_calculator import EnergyModel, CarbonFootprintCalculator
from utils.heuristic_evaluator import evaluar_y_corregir_heuristicas
from services.file_handler import handle_uploaded_file
from utils.debug_logger import DebugTrace  # NUEVO
import os
import uuid
import shutil

main = Blueprint("main", __name__)

energy_model = EnergyModel(
    [1.804551146759771e-07, -3.0220347704227896e-07, 1.4154405902803595e-07],
    [9.412383738420182e-08, -1.5781520809511624e-07, 7.546610037732226e-08],
    [1.3946409007268839e-08, -2.4495186160412765e-08, 1.598790315272048e-08],
    0.120833
)

calculator = CarbonFootprintCalculator()

def detectar_html_unico(base_path: str) -> str:
    html_files = []
    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith(".html"):
                html_files.append(os.path.join(root, file))

    if len(html_files) == 0:
        raise FileNotFoundError("No se encontró ningún archivo .html en el proyecto subido.")
    if len(html_files) > 1:
        raise ValueError(f"Se encontraron múltiples archivos .html: {html_files}. El proyecto debe tener solo uno.")

    return html_files[0]

def copiar_recursos(base_path: str, static_session_dir: str) -> None:
    extensiones_validas = ('.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif')

    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith(extensiones_validas):
                origen = os.path.join(root, file)
                relativo = os.path.relpath(origen, base_path)
                destino = os.path.join(static_session_dir, relativo)
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                shutil.copy2(origen, destino)

def _compute_rating_from_sci(sci_score: float) -> str:
    # Rating basado en SCI Score fijo (misma lógica que ya tienes)
    if sci_score <= 1.2:
        return "A+"
    elif sci_score <= 1.5:
        return "A"
    elif sci_score <= 2.0:
        return "B"
    elif sci_score <= 3.0:
        return "C"
    else:
        return "E"

def _normalize_base_path_for_single_subdir(base_path: str) -> str:
    """
    Si el ZIP extrae una carpeta única (proyecto/...), nos metemos a esa carpeta.
    Mantiene tu comportamiento actual.
    """
    if not base_path or not os.path.isdir(base_path):
        return base_path

    subdirs = [
        d for d in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, d))
    ]
    if len(subdirs) == 1:
        return os.path.join(base_path, subdirs[0])

    return base_path

def _analyze_gui_to_color_data(html_content: str, base_path: str, trace: DebugTrace, label: str):
    """
    Encapsula el pipeline: analyze_gui -> extract_pixels -> classify_colors
    """
    trace.add_step(f"{label}.render_start", {"base_path": base_path})

    pixels = analyze_gui(html_content, base_path=base_path)
    trace.add_step(f"{label}.render_done", {"pixels_type": str(type(pixels))})

    extracted = extract_pixels(pixels)
    trace.add_step(f"{label}.pixels_extracted", {"count": len(extracted) if hasattr(extracted, "__len__") else None})

    color_data = classify_colors(extracted)
    trace.add_step(f"{label}.colors_classified", {
        "distinct_colors": len(color_data) if hasattr(color_data, "__len__") else None
    })
    return color_data

@main.route("/")
def index():
    return render_template("index.html")  # :contentReference[oaicite:2]{index=2}

@main.route("/header")
def header():
    return render_template("header.html")  # :contentReference[oaicite:3]{index=3}

@main.route("/results", methods=["POST"])
def results():
    clean_old_sessions()

    # Debug temporal solo para UI (no logging)
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

    # Si subes ZIP normalmente base_path viene con carpeta session_...
    # Si un día subes .html directo, tu handler devuelve base_path=None, por eso protegemos:
    if base_path:
        base_path = _normalize_base_path_for_single_subdir(base_path)

    # Si base_path sigue siendo None (caso HTML directo), intentamos evitar crash y dar error claro:
    if not base_path:
        flash("Para análisis completo (CSS/imagenes), sube un ZIP con el HTML y sus recursos.", "error")
        trace.add_step("upload.missing_base_path", {})
        return redirect(url_for("main.index"))

    trace.add_step("project.base_path", {"base_path": base_path})

    # Detectar HTML único dentro del proyecto
    html_path = detectar_html_unico(base_path)
    html_filename = os.path.basename(html_path)
    trace.add_step("project.html_detected", {"html_path": html_path, "html_name": html_filename})

    # Parse HTML (componentes)
    components = parse_html(html_content)
    trace.add_step("analysis.html_parsed", {"components_type": str(type(components))})

    # --- GUI ORIGINAL ---
    color_data = _analyze_gui_to_color_data(html_content, base_path=base_path, trace=trace, label="original")

    total_current = energy_model.calculate_power(color_data)
    footprint = calculator.calculate(total_current, time_hours=1)
    sci_score = footprint["sci_score"]

    rating = _compute_rating_from_sci(sci_score)

    trace.add_step("metrics.original", {
        "total_current": total_current,
        "energy_wh": footprint.get("energy_wh"),
        "co2eq_per_use": footprint.get("co2eq_per_use"),
        "sci_score": sci_score,
        "rating": rating
    })

    # --- OPTIMIZACIÓN / PROYECTO CORREGIDO ---
    session_id = str(uuid.uuid4())[:8]
    static_session_dir = f"static/corrected/{session_id}"
    os.makedirs(static_session_dir, exist_ok=True)
    trace.add_step("opt.session_created", {"session_id": session_id, "static_session_dir": static_session_dir})

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

    # --- GUI OPTIMIZADA ---
    color_data_optimized = _analyze_gui_to_color_data(
        html_optimized_content, base_path=static_session_dir, trace=trace, label="optimized"
    )

    optimized_current = energy_model.calculate_power(color_data_optimized)
    optimized_footprint = calculator.calculate(optimized_current, time_hours=1)

    trace.add_step("metrics.optimized", {
        "optimized_current": optimized_current,
        "optimized_energy_wh": optimized_footprint.get("energy_wh"),
        "optimized_co2eq_per_use": optimized_footprint.get("co2eq_per_use"),
        "optimized_sci_score": optimized_footprint.get("sci_score"),
    })

    # --- SALIDA (MISMA ESTRUCTURA QUE YA TIENES) ---
    results = {
        "total_current": total_current,
        "carbon_footprint": footprint["co2eq_per_use"],
        "energy_wh": footprint["energy_wh"],
        "sci_score": footprint["sci_score"],
        "optimized_energy_wh": optimized_footprint["energy_wh"],
        "optimized_co2eq_per_use": optimized_footprint["co2eq_per_use"],
        "optimization_rating": rating,
        "session_id": session_id,
        "html_name": html_filename,
        "heuristicas": resultados_heuristicas,

        # NUEVO: Debug para UI (no rompe nada)
        "debug": trace.to_dict()
    }

    return render_template("results.html", results=results)
