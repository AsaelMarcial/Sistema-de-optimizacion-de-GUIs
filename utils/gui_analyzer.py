import os
import math
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright


def _clamp_int(value, min_v, max_v):
    try:
        v = int(math.ceil(float(value)))
    except Exception:
        v = min_v
    return max(min_v, min(max_v, v))


def analyze_gui(
    html_content: str,
    base_path: str,
    output_image: str,
    initial_viewport_width: int = 1440,
    initial_viewport_height: int = 900,
    wait_ms: int = 700,
    max_viewport_width: int = 3840,
    max_viewport_height: int = 20000,
):
    """
    Renderiza HTML usando Playwright, ajusta viewport automáticamente al tamaño real del documento,
    y guarda una captura exacta SIN scroll.

    Retorna:
      np.ndarray con shape (H, W, 3) en RGB (P-LMLR usa RGB).

    Requisitos:
      - base_path debe ser un directorio válido donde existan los recursos relativos (CSS/imagenes).
      - Playwright + Chromium instalados: python -m playwright install chromium
    """
    if not base_path or not os.path.isdir(base_path):
        raise ValueError("analyze_gui requiere un base_path válido para resolver recursos (CSS/imagenes).")

    # Asegurar directorio del output
    out_dir = os.path.dirname(output_image)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Escribir HTML temporal dentro del base_path para respetar rutas relativas
    temp_html_path = os.path.join(base_path, "__glow_render__.html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    abs_temp = os.path.abspath(temp_html_path)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            page = browser.new_page(
                viewport={"width": int(initial_viewport_width), "height": int(initial_viewport_height)}
            )

            # Carga base
            page.goto(f"file://{abs_temp}", wait_until="load")

            # Quitar scrollbars para que no contaminen el conteo de píxeles
            page.evaluate("""
                () => {
                  document.body.style.overflow = 'hidden';
                  document.documentElement.style.overflow = 'hidden';
                }
            """)

            # Espera corta por estabilidad visual (CSS, fuentes)
            if wait_ms and wait_ms > 0:
                page.wait_for_timeout(int(wait_ms))

            # Medir dimensiones reales del documento (más robusto que solo scrollWidth/scrollHeight)
            dims = page.evaluate("""
                () => {
                  const body = document.body;
                  const html = document.documentElement;

                  const width = Math.max(
                    body ? body.scrollWidth : 0,
                    body ? body.offsetWidth : 0,
                    html ? html.clientWidth : 0,
                    html ? html.scrollWidth : 0,
                    html ? html.offsetWidth : 0
                  );

                  const height = Math.max(
                    body ? body.scrollHeight : 0,
                    body ? body.offsetHeight : 0,
                    html ? html.clientHeight : 0,
                    html ? html.scrollHeight : 0,
                    html ? html.offsetHeight : 0
                  );

                  return { width, height };
                }
            """)

            target_w = _clamp_int(dims.get("width", initial_viewport_width), 320, max_viewport_width)
            target_h = _clamp_int(dims.get("height", initial_viewport_height), 240, max_viewport_height)

            # Ajustar viewport a tamaño real
            page.set_viewport_size({"width": target_w, "height": target_h})

            # Reaplicar overflow hidden y esperar un poco por reflow tras el resize
            page.evaluate("""
                () => {
                  document.body.style.overflow = 'hidden';
                  document.documentElement.style.overflow = 'hidden';
                }
            """)
            page.wait_for_timeout(200)

            # Screenshot EXACTO del viewport ya ajustado (sin full_page)
            page.screenshot(path=output_image)

            browser.close()

        # Convertir a RGB (P-LMLR)
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
