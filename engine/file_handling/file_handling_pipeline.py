import os

from engine.file_handling.services.file_handler import handle_uploaded_file
from engine.file_handling.services.project_assets import (
    normalize_base_path_for_single_subdir,
    detectar_html_unico,
)


def run_file_handling_pipeline(file, session_id: str):
    """
    Retorna:
      - (html_content, base_path, html_path, html_filename) si ok
      - "mensaje de error" si falla
    """
    result = handle_uploaded_file(file, session_id)
    if isinstance(result, str):
        return result

    base_path, _session_id, uploaded_path = result
    normalized_base_path = normalize_base_path_for_single_subdir(base_path)

    try:
        if uploaded_path.lower().endswith(".html"):
            html_path = uploaded_path
        else:
            html_path = detectar_html_unico(normalized_base_path)
    except (FileNotFoundError, ValueError) as exc:
        return str(exc)

    html_filename = os.path.basename(html_path)

    try:
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    except Exception:
        return "No se pudo leer el archivo HTML."

    return html_content, base_path, html_path, html_filename
