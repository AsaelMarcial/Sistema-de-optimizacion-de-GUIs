import os
import numpy as np
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller


def analyze_gui(html_content, output_image="data/output/gui_screenshot.png"):
    """
    Renderiza el HTML proporcionado en un navegador usando Selenium y genera una captura de pantalla.
    Luego, convierte la imagen en una matriz de píxeles.

    Args:
        html_content (str): Contenido HTML a renderizar.
        output_image (str): Ruta donde se guardará la captura de pantalla.

    Returns:
        np.ndarray: Matriz de píxeles de la imagen capturada.
    """
    # Configuración de Selenium
    chromedriver_autoinstaller.install()  # Asegura que el driver esté disponible
    options = Options()
    options.add_argument("--headless")  # Ejecutar en modo headless (sin ventana)
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,720")  # Tamaño de la ventana del navegador

    # Crear un navegador de Selenium
    with webdriver.Chrome(options=options) as driver:
        # Guardar HTML en un archivo temporal
        temp_html_path = "data/input/temp_render.html"
        with open(temp_html_path, "w", encoding="utf-8") as temp_html_file:
            temp_html_file.write(html_content)

        # Abrir el archivo temporal en el navegador
        driver.get(f"file://{os.path.abspath(temp_html_path)}")

        # Tomar una captura de pantalla
        driver.save_screenshot(output_image)

    # Convertir la imagen a una matriz de píxeles
    with Image.open(output_image) as img:
        pixel_array = np.array(img)

    # Retorna la matriz de píxeles
    return pixel_array
