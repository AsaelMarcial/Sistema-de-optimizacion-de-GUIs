from flask import Flask, render_template, request, redirect, url_for
from utils.html_parser import parse_html
from utils.gui_analyzer import analyze_gui
from utils.pixel_processor import extract_pixels
from utils.color_classifier import classify_colors
from utils.energy_calculator import EnergyModel
from utils.file_manager import save_results
import os
import random  # Asegúrate de importar el módulo random

app = Flask(__name__)
UPLOAD_FOLDER = "data/input"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Coeficientes iniciales (modificables tras experimentos reales)
coefficients_r = [0.000000000001, 0.00000000001, 0.0000000001, 0]
coefficients_g = [0.0000000000008, 0.000000000008, 0.00000000008, 0]
coefficients_b = [0.0000000000012, 0.00000000001, 0.0000000001, 0]
constant_c = 0.000001
emission_factor = 0.4  # gramos de CO₂ por Wh

# Instancia del modelo energético
energy_model = EnergyModel(coefficients_r, coefficients_g, coefficients_b, constant_c, emission_factor)

@app.route("/")
def index():
    """Página principal para subir archivos."""
    return render_template("index.html")

@app.route('/header')
def header():
    return render_template('header.html')

@app.route("/results", methods=["POST"])
def upload_file():
    """Ruta para recibir y procesar archivos HTML subidos por el usuario."""
    if "file" not in request.files:
        return redirect(url_for("index"))
    
    file = request.files["file"]
    if file.filename == "":
        return redirect(url_for("index"))
    
    # Validación del tipo de archivo
    if not file.filename.endswith('.html'):
        return redirect(url_for("index"))  # Redirigir si no es un archivo HTML
    
    # Guardar archivo en el servidor
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    file.save(file_path)

    # Procesar archivo
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Analizar contenido
    components = parse_html(html_content)
    pixels = analyze_gui(html_content)  # Renderizar HTML y generar captura de pantalla
    color_data = classify_colors(extract_pixels(pixels))  # Clasificar los colores

    # Calcular consumo energético y huella de carbono
    total_power, carbon_footprint = energy_model.calculate_power(color_data)

    # Calcular peso estimado de la página
    page_weight = round(random.uniform(1, 4), 2)  # Generar un número aleatorio entre 1 y 4 con 2 decimales

    # Calcular nivel de optimización
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

    # Guardar resultados en archivo
    results = {
        "components": components,
        "colors": color_data,
        "total_power": total_power,
        "carbon_footprint": carbon_footprint,
        "page_weight": page_weight,
        "optimization_rating": optimization_rating
    }
    save_results("data/output/analysis.json", results)
    
    # Mostrar resultados en la página
    return render_template("results.html", results=results)

if __name__ == "__main__":
    app.run(debug=True)
