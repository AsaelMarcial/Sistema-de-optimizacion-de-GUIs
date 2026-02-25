import os
from bs4 import BeautifulSoup

from app.config import get_output_dir
from engine.analysis.utils.color_utils import (
    adjust_gradient_rgb_line,
    brighten_color,
    contrast_ratio,
    detect_body_background_rgb,
    extract_hex_colors,
    hex_to_rgb,
    is_energy_intensive,
    is_light_color,
    reduce_energy_intensity,
    rgb_string_to_tuple,
    rgb_to_css,
)
from engine.core.utils.debug_logger import DebugTrace

trace = DebugTrace(enabled=True)


def evaluar_y_corregir_heuristicas(html_content, output_path, base_path, session_id):

    # 1) Preparación de salida por sesión
    if session_id:
        html_name = os.path.basename(output_path)
        output_dir = get_output_dir(session_id)
        output_path = os.path.join(output_dir, html_name)
        os.makedirs(output_dir, exist_ok=True)

    # 2) Parseo HTML y contadores de evaluación
    soup = BeautifulSoup(html_content, "html.parser")
    resultados = []
    detalles_colores = []
    detalles_tamanos = []
    detalles_decoraciones = []

    colores_bril = 0
    colores_tot = 0
    componentes_grandes = 0
    estilos_eliminados = 0

    body_bg = detect_body_background_rgb(soup)
    aplicar_dark_mode = is_light_color(body_bg)

    if aplicar_dark_mode:
        body = soup.find("body")
        if body:
            body["style"] = "background-color: rgb(0,0,0)"

    def procesar_rgb(rgb, contexto, tipo=None, original_valor=None):
        nonlocal colores_bril
        if is_energy_intensive(rgb):
            colores_bril += 1
            rgb_mod = reduce_energy_intensity(rgb, factor=0.5)
            if tipo and original_valor:
                detalles_colores.append(f"{contexto}: {original_valor} → {rgb_to_css(rgb_mod)} ({tipo})")
            else:
                detalles_colores.append(f"{contexto}: {rgb} → {rgb_mod}")
            return rgb_mod
        return rgb

    # 3) Transformación de CSS inline (style="...")
    for tag in soup.find_all(style=True):
        styles = {k.strip(): v.strip() for k, v in [x.split(":") for x in tag["style"].split(";") if ":" in x]}
        new_styles = {}

        for clave, valor in styles.items():
            rgb = None
            if "rgb(" in valor:
                rgb = rgb_string_to_tuple(valor)
            elif "#" in valor:
                rgb = hex_to_rgb(valor)

            if rgb:
                colores_tot += 1
                if clave == "color" and aplicar_dark_mode:
                    contraste = contrast_ratio(rgb, (0, 0, 0))
                    if contraste < 4.5:
                        rgb = brighten_color(rgb, 4.5, (0, 0, 0))
                elif "background" in clave:
                    rgb = procesar_rgb(rgb, f"<{tag.name}>", tipo=clave, original_valor=valor)

            if "width" in clave or "height" in clave:
                try:
                    val = int(valor.replace("px", "").strip())
                    if val > 500:
                        val = 400 if "width" in clave else 300
                        valor = f"{val}px"
                        componentes_grandes += 1
                        detalles_tamanos.append(f"<{tag.name}>: {clave} ajustado a {valor}")
                except Exception:
                    pass

            if any(x in clave for x in ["box-shadow", "border", "gradient"]):
                estilos_eliminados += 1
                detalles_decoraciones.append(f"Eliminado {clave} en <{tag.name}>")
                continue

            if rgb:
                valor = rgb_to_css(rgb)

            new_styles[clave] = valor

        if new_styles:
            tag["style"] = "; ".join(f"{k}: {v}" for k, v in new_styles.items())
        else:
            del tag["style"]

    # 4) Transformación de CSS embebido (<style>...</style>)
    for style_tag in soup.find_all("style"):
        if not style_tag.string:
            continue
        lines = style_tag.string.split("\n")
        new_lines = []
        for line in lines:
            line = adjust_gradient_rgb_line(line, "style embebido", detalles_colores)

            if "rgb(" in line or "#" in line:
                parts = line.split("rgb(")
                for index in range(1, len(parts)):
                    rgb_val = parts[index].split(")")[0]
                    try:
                        rgb = tuple(map(int, rgb_val.split(",")))
                        colores_tot += 1
                        rgb = procesar_rgb(rgb, "style embebido", original_valor=f"rgb({rgb_val})")
                        line = line.replace(f"rgb({rgb_val})", rgb_to_css(rgb))
                    except ValueError:
                        continue

                for hex_color in extract_hex_colors(line):
                    rgb = hex_to_rgb(hex_color)
                    if rgb:
                        colores_tot += 1
                        rgb_mod = procesar_rgb(rgb, "style embebido", original_valor=hex_color)
                        line = line.replace(hex_color, rgb_to_css(rgb_mod))

            if any(x in line for x in ["box-shadow", "border", "gradient"]):
                estilos_eliminados += 1
                detalles_decoraciones.append("Eliminada decoración en style embebido")
                continue
            new_lines.append(line)
        style_tag.string = "\n".join(new_lines)

    # 5) Transformación de CSS externo referenciado por <link>
    for link in soup.find_all("link", href=True):
        href = link["href"]
        if href.startswith(("http://", "https://", "//")):
            continue
        if href.endswith(".css"):
            ruta_css = os.path.join(base_path, href.lstrip("/"))
            if os.path.exists(ruta_css):
                with open(ruta_css, "r", encoding="utf-8") as file:
                    lines = file.readlines()
                new_lines = []
                for line in lines:
                    line = adjust_gradient_rgb_line(line, "CSS externo", detalles_colores)
                    if "rgb(" in line or "#" in line:
                        parts = line.split("rgb(")
                        for index in range(1, len(parts)):
                            rgb_val = parts[index].split(")")[0]
                            try:
                                rgb = tuple(map(int, rgb_val.split(",")))
                                colores_tot += 1
                                rgb = procesar_rgb(rgb, "CSS externo", original_valor=f"rgb({rgb_val})")
                                line = line.replace(f"rgb({rgb_val})", rgb_to_css(rgb))
                            except ValueError:
                                continue

                        for hex_color in extract_hex_colors(line):
                            rgb = hex_to_rgb(hex_color)
                            if rgb:
                                colores_tot += 1
                                rgb_mod = procesar_rgb(rgb, "CSS externo", original_valor=hex_color)
                                line = line.replace(hex_color, rgb_to_css(rgb_mod))

                    if any(x in line for x in ["box-shadow", "border", "gradient"]):
                        estilos_eliminados += 1
                        detalles_decoraciones.append("Eliminada decoración en CSS externo")
                        continue
                    new_lines.append(line)
                with open(ruta_css, "w", encoding="utf-8") as file:
                    file.writelines(new_lines)

    # 6) Normalización de rutas relativas en href/src
    for tag in soup.find_all(["link", "img"]):
        attr = "href" if tag.name == "link" else "src"
        if tag.has_attr(attr):
            path = tag[attr]
            if path.startswith(("http://", "https://", "//", "data:")):
                continue
            clean_path = os.path.normpath(path.lstrip("/")).replace("\\", "/")
            while clean_path.startswith("../") or clean_path.startswith("./"):
                if clean_path.startswith("../"):
                    clean_path = clean_path[3:]
                elif clean_path.startswith("./"):
                    clean_path = clean_path[2:]
            tag[attr] = clean_path

    with open(output_path, "w", encoding="utf-8") as file:
        file.write(str(soup))

    # 7) Construcción de resultados de heurísticas
    porcentaje_bril = (colores_bril / colores_tot) * 100 if colores_tot > 0 else 0

    resultados.append(
        {
            "nombre": "Modo oscuro",
            "cumple": not aplicar_dark_mode,
            "recomendacion": "Se aplicó dark mode por fondo claro." if aplicar_dark_mode else "No fue necesario aplicar dark mode.",
        }
    )

    resultados.append(
        {
            "nombre": "Minimizar el uso de colores brillantes",
            "cumple": porcentaje_bril < 30,
            "recomendacion": f"Se redujo la intensidad de {colores_bril} colores.",
            "detalles": detalles_colores,
        }
    )
    resultados.append(
        {
            "nombre": "Reducción de tamaños excesivos",
            "cumple": componentes_grandes == 0,
            "recomendacion": f"Se ajustaron {componentes_grandes} elementos grandes.",
            "detalles": detalles_tamanos,
        }
    )
    resultados.append(
        {
            "nombre": "Uso moderado de decoraciones visuales",
            "cumple": estilos_eliminados == 0,
            "recomendacion": f"Se eliminaron {estilos_eliminados} estilos innecesarios.",
            "detalles": detalles_decoraciones,
        }
    )

    trace.add_step(
        "transformed.heuristics_applied",
        {
            "resultados": resultados,
        },
    )

    return resultados
