from flask import Flask, render_template, request, redirect, url_for
from utils.html_parser import parse_html
from utils.gui_analyzer import analyze_gui
from utils.pixel_processor import extract_pixels
from utils.color_classifier import classify_colors
from utils.file_manager import save_results
import os

app = Flask(__name__)
UPLOAD_FOLDER = "data/input"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/")
def index():
    """Página principal para subir archivos."""
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    """Ruta para recibir y procesar archivos HTML subidos por el usuario."""
    if "file" not in request.files:
        return redirect(url_for("index"))
    
    file = request.files["file"]
    if file.filename == "":
        return redirect(url_for("index"))
    
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

    # Guardar resultados en archivo
    results = {
        "components": components,
        "colors": color_data,
    }
    save_results("data/output/analysis.json", results)
    
    # Mostrar resultados en la página
    return render_template("results.html", results=results)

if __name__ == "__main__":
    app.run(debug=True)
