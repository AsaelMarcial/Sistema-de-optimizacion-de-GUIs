import os
import time
import numpy as np
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def analyze_gui(
    html_content: str,
    base_path: str,
    output_image: str,
    wait_seconds: float = 1.0
):
    """
    Renderiza el HTML en Selenium tomando como raíz `base_path`,
    para que los recursos relativos (CSS/imagenes) resuelvan correctamente.
    Devuelve matriz (H, W, 3) RGB y guarda screenshot en `output_image`.
    """
    if not base_path or not os.path.isdir(base_path):
        raise ValueError("analyze_gui requiere un base_path válido para resolver recursos (CSS/imagenes).")

    # Asegurar output dir
    out_dir = os.path.dirname(output_image)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Escribir HTML temporal DENTRO del proyecto (clave para CSS/imagenes relativos)
    temp_html_path = os.path.join(base_path, "__glow_render__.html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--hide-scrollbars")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        file_url = "file:///" + os.path.abspath(temp_html_path).replace("\\", "/")
        driver.get(file_url)

        # Espera simple (luego lo refinamos con Playwright/networkidle)
        time.sleep(wait_seconds)

        # Ocultar overflow para evitar barras
        driver.execute_script("""
            document.documentElement.style.overflow = 'hidden';
            document.body.style.overflow = 'hidden';
        """)

        driver.save_screenshot(output_image)

        # Forzar RGB (P-LMLR usa solo RGB)
        with Image.open(output_image) as img:
            img = img.convert("RGB")
            pixel_array = np.array(img)

        return pixel_array

    finally:
        driver.quit()
        # Limpieza del temp (no queremos basura dentro del proyecto)
        try:
            os.remove(temp_html_path)
        except Exception:
            pass
