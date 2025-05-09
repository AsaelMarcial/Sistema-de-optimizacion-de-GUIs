import os
import zipfile
from werkzeug.utils import secure_filename
from config import ALLOWED_EXTENSIONS, ALLOWED_ZIP_CONTENT
import uuid

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS

def handle_uploaded_file(file):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return "Archivo no permitido"

    session_id = str(uuid.uuid4())
    base_path = os.path.join("data", "input", f"session_{session_id}")
    os.makedirs(base_path, exist_ok=True)

    file_path = os.path.join(base_path, secure_filename(file.filename))
    file.save(file_path)

    if ext == ".html":
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        return html_content, None

    elif ext == ".zip":
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for member in zip_ref.infolist():
                    if member.is_dir():
                        continue  # Ignorar carpetas

                    if ".." in member.filename or member.filename.startswith("/"):
                        return "ZIP inseguro"

                    ext = os.path.splitext(member.filename)[1].lower()
                    if ext not in ALLOWED_ZIP_CONTENT:
                        return f"Archivo no permitido: {member.filename}"
                zip_ref.extractall(base_path)
        except zipfile.BadZipFile:
            return "ZIP corrupto"

        html_file = None
        for root, _, files in os.walk(base_path):
            for f in files:
                if f.endswith(".html"):
                    html_file = os.path.join(root, f)
                    break
        if not html_file:
            return "No se encontró HTML en el ZIP"

        with open(html_file, "r", encoding="utf-8") as f:
            html_content = f.read()
        return html_content, base_path
