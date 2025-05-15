from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.file_handler import handle_uploaded_file
from services.session_cleaner import clean_old_sessions
from utils.html_parser import parse_html
from utils.gui_analyzer import analyze_gui
from utils.pixel_processor import extract_pixels
from utils.color_classifier import classify_colors
from utils.energy_calculator import EnergyModel
from utils.file_manager import save_results
from utils.heuristic_evaluator import evaluar_y_corregir_heuristicas
import os
import uuid
import random
import shutil

main = Blueprint("main", __name__)

energy_model = EnergyModel(
    [1e-12, 1e-11, 1e-10, 0],
    [8e-13, 8e-12, 8e-11, 0],
    [1.2e-12, 1e-11, 1e-10, 0],
    1e-6,
    emission_factor=0.4
)

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

    # Si base_path tiene solo una subcarpeta, bajamos a ella automáticamente
    subdirs = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    if len(subdirs) == 1:
        base_path = os.path.join(base_path, subdirs[0])

    # Detectar HTML único
    html_path = detectar_html_unico(base_path)
    html_filename = os.path.basename(html_path)

    # Análisis habitual
    components = parse_html(html_content)
    pixels = analyze_gui(html_content, base_path=base_path)
    color_data = classify_colors(extract_pixels(pixels))
    total_power, carbon_footprint = energy_model.calculate_power(color_data)
    page_weight = round(random.uniform(1, 4), 2)

    if carbon_footprint < 10 and page_weight < 1:
        rating = "A+"
    elif carbon_footprint < 20 and page_weight < 2:
        rating = "A"
    elif carbon_footprint < 40 and page_weight < 3:
        rating = "B"
    elif carbon_footprint < 60 and page_weight < 4:
        rating = "C"
    else:
        rating = "E"

    session_id = str(uuid.uuid4())[:8]
    static_session_dir = f"static/corrected/{session_id}"
    os.makedirs(static_session_dir, exist_ok=True)

    # Leer el HTML original
    with open(html_path, "r", encoding="utf-8") as f:
        html_real = f.read()

    # Aplicar heurísticas
    resultados_heuristicas = evaluar_y_corregir_heuristicas(html_real, html_path, base_path, session_id)

    # Copiar recursos detectados
    copiar_recursos(base_path, static_session_dir)

    # Crear ZIP con el proyecto corregido
    zip_output_path = f"static/corrected/{session_id}.zip"
    shutil.make_archive(zip_output_path.replace(".zip", ""), 'zip', static_session_dir)


    results = {
        "components": components,
        "colors": color_data,
        "total_power": total_power,
        "carbon_footprint": carbon_footprint,
        "page_weight": page_weight,
        "optimization_rating": rating,
        "heuristicas": resultados_heuristicas,
        "session_id": session_id,
        "html_name": html_filename
    }

    return render_template("results.html", results=results)
