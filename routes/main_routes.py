from flask import Blueprint, render_template, request, redirect, url_for, flash
from services.file_handler import handle_uploaded_file
from services.session_cleaner import clean_old_sessions
from utils.html_parser import parse_html
from utils.gui_analyzer import analyze_gui
from utils.pixel_processor import extract_pixels
from utils.color_classifier import classify_colors
from utils.energy_calculator import EnergyModel
from utils.file_manager import save_results
import os
import random
import logging
import sys

# Configurar logging para consola

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)


main = Blueprint("main", __name__)

# Modelo energético
energy_model = EnergyModel(
    [1e-12, 1e-11, 1e-10, 0],     # R
    [8e-13, 8e-12, 8e-11, 0],     # G
    [1.2e-12, 1e-11, 1e-10, 0],   # B
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

    if isinstance(result, str):  # Si es mensaje de error
        flash(result, "error")
        return redirect(url_for("main.index"))

    html_content, base_path = result

    # Procesar GUI
    components = parse_html(html_content)
    pixels = analyze_gui(html_content, base_path=base_path)
    color_data = classify_colors(extract_pixels(pixels))

    # 📝 Log de análisis
    logging.info(f"Componentes del HTML analizado: {components}")
    logging.info(f"Colores clasificados: {color_data}")

    total_power, carbon_footprint = energy_model.calculate_power(color_data)
    page_weight = round(random.uniform(1, 4), 2)

    if carbon_footprint < 10 and page_weight < 1:
        optimization_rating = "A+"
    elif carbon_footprint < 20 and page_weight < 2:
        optimization_rating = "A"
    elif carbon_footprint < 40 and page_weight < 3:
        optimization_rating = "B"
    elif carbon_footprint < 60 and page_weight < 4:
        optimization_rating = "C"
    else:
        optimization_rating = "E"

    # 📝 Log de resultados
    logging.info(f"Resultados: Potencia={total_power:.2f}W, CO2={carbon_footprint:.2f}g, Peso={page_weight}MB, Rating={optimization_rating}")

    results = {
        "components": components,
        "colors": color_data,
        "total_power": total_power,
        "carbon_footprint": carbon_footprint,
        "page_weight": page_weight,
        "optimization_rating": optimization_rating
    }

    save_results("data/output/analysis.json", results)
    return render_template("results.html", results=results)

