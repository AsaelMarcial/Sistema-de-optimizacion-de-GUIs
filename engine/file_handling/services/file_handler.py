import os
import zipfile

from werkzeug.utils import secure_filename

from app.config import ALLOWED_EXTENSIONS, ALLOWED_ZIP_CONTENT, get_input_dir


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


def handle_uploaded_file(file, session_id: str):
    """
    Retorna:
      - (base_path, session_id, uploaded_path) si ok
      - "mensaje de error" si falla
    """
    if not file or not file.filename:
        return "No se seleccionó ningún archivo."

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return "Archivo no permitido"

    base_path = get_input_dir(session_id)
    os.makedirs(base_path, exist_ok=True)

    # Guardar upload
    safe_name = secure_filename(file.filename)
    file_path = os.path.join(base_path, safe_name)
    file.save(file_path)

    # Caso HTML suelto
    if ext == ".html":
        return base_path, session_id, file_path

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

        return base_path, session_id, file_path

    return "Archivo no permitido"
