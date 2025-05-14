
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
import zipfile

main = Blueprint("main", __name__)

energy_model = EnergyModel(
    [1e-12, 1e-11, 1e-10, 0],
    [8e-13, 8e-12, 8e-11, 0],
    [1.2e-12, 1e-11, 1e-10, 0],
    1e-6,
    emission_factor=0.4
)

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

    html_filename = next((f for f in os.listdir(base_path) if f.endswith(".html")), "index.html")
    corrected_path = os.path.join(base_path, html_filename)

    with open(corrected_path, "r", encoding="utf-8") as f:
        html_real = f.read()

    resultados_heuristicas = evaluar_y_corregir_heuristicas(html_real, corrected_path, base_path)


    shutil.copytree(base_path, static_session_dir, dirs_exist_ok=True)

    # Crear un ZIP con el proyecto corregido
    zip_output_path = f"static/corrected/{session_id}.zip"
    with zipfile.ZipFile(zip_output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(static_session_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, static_session_dir)
                zipf.write(abs_path, rel_path)

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
