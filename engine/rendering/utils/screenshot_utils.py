import os


def ensure_output_dir(output_image: str) -> None:
    out_dir = os.path.dirname(output_image)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)


def write_temp_html(html_content: str, base_path: str, filename: str = "__glow_render__.html") -> str:
    if not base_path or not os.path.isdir(base_path):
        raise ValueError("render_gui requiere un base_path válido para resolver recursos (CSS/imagenes).")

    temp_html_path = os.path.join(base_path, filename)
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return os.path.abspath(temp_html_path)


def remove_temp_html(temp_html_path: str) -> None:
    if temp_html_path and os.path.exists(temp_html_path):
        os.remove(temp_html_path)
