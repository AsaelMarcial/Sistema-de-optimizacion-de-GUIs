import os
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright


def analyze_gui(
    html_content: str,
    base_path: str,
    output_image: str,
    viewport_width: int = 1440,
    viewport_height: int = 900,
    wait_ms: int = 1000,
):
    """
    Renderiza HTML usando Playwright y genera captura REAL full-page.
    Retorna np.ndarray (H, W, 3) en RGB.
    P-LMLR usa solo RGB.
    """

    if not base_path or not os.path.isdir(base_path):
        raise ValueError("analyze_gui requiere un base_path válido para resolver recursos (CSS/imagenes).")

    # Asegurar output dir
    out_dir = os.path.dirname(output_image)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # HTML temporal dentro del base_path (clave para rutas relativas)
    temp_html_path = os.path.join(base_path, "__glow_render__.html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    abs_temp = os.path.abspath(temp_html_path)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            page = browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height}
            )

            page.goto(f"file://{abs_temp}", wait_until="load")

            # Quitar scrollbars / evitar que afecten conteo
            page.evaluate("""
                document.body.style.overflow = 'hidden';
                document.documentElement.style.overflow = 'hidden';
            """)

            # Espera simple (después podemos cambiar a networkidle si quieres)
            page.wait_for_timeout(wait_ms)

            # Full page real
            page.screenshot(path=output_image, full_page=True)

            browser.close()

        # Convertir a RGB para pipeline (evita RGBA)
        with Image.open(output_image) as img:
            img = img.convert("RGB")
            pixel_array = np.array(img)

        return pixel_array

    finally:
        # Limpieza del temporal
        try:
            os.remove(temp_html_path)
        except Exception:
            pass
