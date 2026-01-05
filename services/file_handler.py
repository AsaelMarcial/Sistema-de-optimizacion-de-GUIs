import os
import zipfile
import uuid
from werkzeug.utils import secure_filename
from config import ALLOWED_EXTENSIONS, ALLOWED_ZIP_CONTENT


def allowed_file(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS


def _is_safe_zip_member(member_name: str) -> bool:
    """
    Evita Zip Slip (../) y rutas absolutas.
    Normaliza separadores para Windows/Linux.
    """
    name = member_name.replace("\\", "/")

    # Evitar rutas absolutas o unidades tipo C:
    if name.startswith("/") or (":" in name.split("/")[0]):
        return False

    # Evitar traversal
    parts = [p for p in name.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return False

    return True


def _validate_zip_members(zip_ref: zipfile.ZipFile) -> str | None:
    """
    Valida que los archivos dentro del ZIP tengan extensiones permitidas.
    Retorna error string si algo falla; None si ok.
    """
    for member in zip_ref.infolist():
        if member.is_dir():
            continue

        if not _is_safe_zip_member(member.filename):
            return f"ZIP inseguro: {member.filename}"

        ext = os.path.splitext(member.filename)[1].lower()
        if ext and (ext not in ALLOWED_ZIP_CONTENT):
            return f"Archivo no permitido en ZIP: {member.filename}"

    return None


def _find_html_files(base_path: str) -> list[str]:
    html_files = []
    for root, _, files in os.walk(base_path):
        for f in files:
            if f.lower().endswith(".html"):
                html_files.append(os.path.join(root, f))
    return html_files


def handle_uploaded_file(file):
    """
    Retorna:
      - (html_content, base_path) si ok
      - "mensaje de error" si falla
    """
    if not file or not file.filename:
        return "No se seleccionó ningún archivo."

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return "Archivo no permitido"

    session_id = str(uuid.uuid4())
    base_path = os.path.join("data", "input", f"session_{session_id}")
    os.makedirs(base_path, exist_ok=True)

    # Guardar upload
    safe_name = secure_filename(file.filename)
    file_path = os.path.join(base_path, safe_name)
    file.save(file_path)

    # Caso HTML suelto (lo dejamos consistente: base_path no es None)
    if ext == ".html":
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return html_content, base_path
        except Exception:
            return "No se pudo leer el archivo HTML."

    # Caso ZIP
    if ext == ".zip":
        try:
            with zipfile.ZipFile(file_path, "r") as zip_ref:
                err = _validate_zip_members(zip_ref)
                if err:
                    return err

                zip_ref.extractall(base_path)
        except zipfile.BadZipFile:
            return "ZIP corrupto"
        except Exception:
            return "No se pudo extraer el ZIP"

        # Buscar HTML dentro del ZIP
        html_files = _find_html_files(base_path)
        if not html_files:
            return "No se encontró HTML en el ZIP"

        # Si hay más de uno, no decido aquí: solo lo reporto claro.
        if len(html_files) > 1:
            return f"Se encontraron múltiples archivos .html en el ZIP: {html_files}"

        html_file = html_files[0]
        try:
            with open(html_file, "r", encoding="utf-8") as f:
                html_content = f.read()
            return html_content, base_path
        except Exception:
            return "No se pudo leer el HTML dentro del ZIP."

    return "Archivo no permitido"
