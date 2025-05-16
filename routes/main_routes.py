from flask import Blueprint, render_template, request, flash, redirect, url_for
from services.session_cleaner import clean_old_sessions
from utils.html_parser import parse_html
from utils.gui_analyzer import analyze_gui
from utils.pixel_processor import extract_pixels
from utils.color_classifier import classify_colors
from utils.energy_calculator import EnergyModel, CarbonFootprintCalculator
from utils.heuristic_evaluator import evaluar_y_corregir_heuristicas
from services.file_handler import handle_uploaded_file
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

def detectar_html_unico(base_path):
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

def copiar_recursos(base_path, static_session_dir):
    extensiones_validas = ('.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif')

    for root, dirs, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith(extensiones_validas):
                origen = os.path.join(root, file)
                relativo = os.path.relpath(origen, base_path)
                destino = os.path.join(static_session_dir, relativo)
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                shutil.copy2(origen, destino)

@main.route("/")
def index():
    return render_template("index.html")

@main.route("/header")
def header():
    return render_template("header.html")

@main.route("/results", methods=["POST"])
def results():
    clean_old_sessions()

    file = request.files.get("file")
    if not file:
        flash("No se seleccionó ningún archivo.", "error")
        return redirect(url_for("main.index"))

    result = handle_uploaded_file(file)
    if isinstance(result, str):
        flash(result, "error")
        return redirect(url_for("main.index"))

    html_content, base_path = result

    subdirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if len(subdirs) == 1:
        base_path = os.path.join(base_path, subdirs[0])

    html_path = detectar_html_unico(base_path)
    html_filename = os.path.basename(html_path)

    components = parse_html(html_content)
    pixels = analyze_gui(html_content, base_path=base_path)
    color_data = classify_colors(extract_pixels(pixels))

    # Consumo GUI evaluada (por 1 hora, 1 usuario)
    total_current = energy_model.calculate_power(color_data)
    footprint = calculator.calculate(total_current, time_hours=1, num_users=1, daily_uses=1)
    sci_score = footprint["sci_score"]

    # Rating basado solo en SCI Score
    if sci_score <= 1.2:
        rating = "A+"
    elif sci_score <= 1.5:
        rating = "A"
    elif sci_score <= 2.0:
        rating = "B"
    elif sci_score <= 3.0:
        rating = "C"
    else:
        rating = "E"

    session_id = str(uuid.uuid4())[:8]
    static_session_dir = f"static/corrected/{session_id}"
    os.makedirs(static_session_dir, exist_ok=True)

    # Aplicar heurísticas y crear proyecto optimizado
    resultados_heuristicas = evaluar_y_corregir_heuristicas(html_content, html_path, base_path, session_id)
    copiar_recursos(base_path, static_session_dir)

    # Crear ZIP del proyecto optimizado
    zip_output_path = f"static/corrected/{session_id}.zip"
    shutil.make_archive(zip_output_path.replace(".zip", ""), 'zip', static_session_dir)

    # RE-ANALIZAR la GUI optimizada desde el archivo optimizado generado
    html_optimized_path = os.path.join(static_session_dir, html_filename)
    with open(html_optimized_path, "r", encoding="utf-8") as f:
        html_optimized_content = f.read()

    pixels_optimized = analyze_gui(html_optimized_content, base_path=static_session_dir)
    color_data_optimized = classify_colors(extract_pixels(pixels_optimized))
    optimized_current = energy_model.calculate_power(color_data_optimized)
    optimized_footprint = calculator.calculate(optimized_current, time_hours=1, num_users=1, daily_uses=1)

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
        "heuristicas": resultados_heuristicas
    }

    return render_template("results.html", results=results)
