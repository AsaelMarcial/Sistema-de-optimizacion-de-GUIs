import os
import numpy as np
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller

def analyze_gui(html_content, output_image="data/output/gui_screenshot.png", base_path=None):
    """
    Renderiza el HTML proporcionado usando Selenium y genera una captura de pantalla.
    Luego convierte la imagen en una matriz de píxeles (np.ndarray).

    Args:
        html_content (str): Contenido HTML a renderizar.
        output_image (str): Ruta de salida para la captura de pantalla.
        base_path (str, opcional): Ruta base si el HTML necesita recursos locales.

    Returns:
        np.ndarray: Matriz de píxeles de la GUI renderizada.
    """
    chromedriver_autoinstaller.install()
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")

    # Guardar HTML temporal en ruta adecuada
    if base_path:
        temp_html_path = os.path.join(base_path, "temp_render.html")
    else:
        temp_html_path = "data/input/temp_render.html"

    with open(temp_html_path, "w", encoding="utf-8") as temp_html_file:
        temp_html_file.write(html_content)

    # Lanzar navegador y capturar imagen
    with webdriver.Chrome(options=options) as driver:
        driver.get(f"file://{os.path.abspath(temp_html_path)}")
        driver.save_screenshot(output_image)

    # Convertir imagen en matriz de píxeles
    with Image.open(output_image) as img:
        pixel_array = np.array(img)

    return pixel_array
