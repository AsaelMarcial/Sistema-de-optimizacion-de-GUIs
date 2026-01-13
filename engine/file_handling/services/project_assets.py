import os
import shutil


def normalize_base_path_for_single_subdir(base_path: str) -> str:
    """
    Si el ZIP extrae una sola carpeta (proyecto/...), entra a esa carpeta.
    """
    if not base_path or not os.path.isdir(base_path):
        return base_path

    subdirs = [
        d for d in os.listdir(base_path)
        if os.path.isdir(os.path.join(base_path, d))
    ]
    if len(subdirs) == 1:
        return os.path.join(base_path, subdirs[0])

    return base_path


def detectar_html_unico(base_path: str) -> str:
    html_files = []
    for root, _, files in os.walk(base_path):
        for file in files:
            if file.lower().endswith(".html"):
                html_files.append(os.path.join(root, file))

    if len(html_files) == 0:
        raise FileNotFoundError("No se encontró ningún archivo .html en el proyecto subido.")
    if len(html_files) > 1:
        raise ValueError(
            f"Se encontraron múltiples archivos .html: {html_files}. El proyecto debe tener solo uno."
        )

    return html_files[0]


def copiar_recursos(
    input_dir: str,
    output_dir: str,
    static_session_dir: str | None = None,
    overwrite_output: bool = True,
) -> None:
    extensiones_validas = ('.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.webp', '.gif')

    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith(extensiones_validas):
                origen = os.path.join(root, file)
                relativo = os.path.relpath(origen, input_dir)
                destino = os.path.join(output_dir, relativo)
                if not overwrite_output and os.path.exists(destino):
                    continue
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                shutil.copy2(origen, destino)

    if static_session_dir:
        for root, _, files in os.walk(output_dir):
            for file in files:
                if file.lower().endswith(extensiones_validas):
                    origen = os.path.join(root, file)
                    relativo = os.path.relpath(origen, output_dir)
                    destino = os.path.join(static_session_dir, relativo)
                    os.makedirs(os.path.dirname(destino), exist_ok=True)
                    shutil.copy2(origen, destino)
