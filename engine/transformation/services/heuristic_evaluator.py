import os
import re
from bs4 import BeautifulSoup

from app.config import get_output_dir
from engine.recommendations.utils.color_utils import (
    parse_rgb,
    rgb_to_css,
    is_light_color,
    contrast_ratio,
    brighten_color,
)

def rgb_string_to_tuple(color_str):
    color_str = color_str.strip().lower().replace("rgb(", "").replace(")", "")
    try:
        return tuple(map(int, color_str.split(",")))
    except:
        return None

def hex_to_rgb(hex_color):
    hex_color = hex_color.strip().lstrip('#')
    if len(hex_color) == 3:
        hex_color = ''.join([c * 2 for c in hex_color])
    try:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    except:
        return None

def reduce_energy_intensity(rgb, factor=0.5):
    r, g, b = rgb
    r = int(r + (128 - r) * factor)
    g = int(g + (128 - g) * factor)
    b = int(b + (128 - b) * factor)
    return (r, g, b)

def is_energy_intensive(rgb):
    return max(rgb) > 200 or is_light_color(rgb)

def ajustar_gradiente_correcto(linea, contexto, detalles_colores):
    if "linear-gradient" in linea and "rgb(" in linea:
        partes = linea.split("rgb(")
        nuevas_partes = [partes[0]]
        for i in range(1, len(partes)):
            rgb_val = partes[i].split(")")[0]
            try:
                rgb = tuple(map(int, rgb_val.split(",")))
                if is_energy_intensive(rgb):
                    factor = 0.5 if max(rgb) > 240 else 0.3
                    rgb_mod = reduce_energy_intensity(rgb, factor=factor)
                    nuevas_partes.append(f"{rgb_mod[0]},{rgb_mod[1]},{rgb_mod[2]})".join(partes[i].split(")", 1)))
                    detalles_colores.append(f"{contexto}: rgb({rgb_val}) → {rgb_to_css(rgb_mod)} (gradiente)")
                else:
                    nuevas_partes.append("rgb(" + partes[i])
            except:
                nuevas_partes.append("rgb(" + partes[i])
        linea = "".join(nuevas_partes)
    return linea

def detectar_fondo_body(soup):
    body = soup.find('body')
    if body and 'style' in body.attrs:
        styles = {k.strip(): v.strip() for k,v in [x.split(":") for x in body['style'].split(";") if ":" in x]}
        if 'background-color' in styles:
            rgb = rgb_string_to_tuple(styles['background-color'])
            if rgb:
                return rgb
    return (255, 255, 255)

def evaluar_y_corregir_heuristicas(html_content, output_path, base_path, session_id):
    if session_id:
        html_name = os.path.basename(output_path)
        output_dir = get_output_dir(session_id)
        output_path = os.path.join(output_dir, html_name)
        os.makedirs(output_dir, exist_ok=True)

    soup = BeautifulSoup(html_content, "html.parser")
    resultados = []
    detalles_colores = []
    detalles_tamanos = []
    detalles_decoraciones = []

    colores_bril = 0
    colores_tot = 0
    componentes_grandes = 0
    estilos_eliminados = 0

    body_bg = detectar_fondo_body(soup)
    aplicar_dark_mode = is_light_color(body_bg)

    if aplicar_dark_mode:
        body = soup.find('body')
        if body:
            body['style'] = f"background-color: rgb(0,0,0)"

    # Función auxiliar para procesar colores RGB
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

    # Optimización de CSS inline    
    for tag in soup.find_all(style=True):
        styles = {k.strip(): v.strip() for k,v in [x.split(":") for x in tag['style'].split(";") if ":" in x]}
        new_styles = {}

        for clave, valor in styles.items():
            rgb = None
            if "rgb(" in valor:
                rgb = rgb_string_to_tuple(valor)
            elif "#" in valor:
                rgb = hex_to_rgb(valor)

            if rgb:
                colores_tot += 1
                if clave == 'color' and aplicar_dark_mode:
                    contrast = contrast_ratio(rgb, (0, 0, 0))
                    if contrast < 4.5:
                        rgb = brighten_color(rgb, 4.5, (0, 0, 0))
                elif 'background' in clave:
                    rgb = procesar_rgb(rgb, f"<{tag.name}>", tipo=clave, original_valor=valor)

            if 'width' in clave or 'height' in clave:
                try:
                    val = int(valor.replace("px", "").strip())
                    if val > 500:
                        val = 400 if 'width' in clave else 300
                        valor = f"{val}px"
                        componentes_grandes += 1
                        detalles_tamanos.append(f"Reducción de {clave} en <{tag.name}> a {valor}")
                except:
                    pass

            if any(x in clave for x in ["box-shadow", "border", "gradient"]):
                estilos_eliminados += 1
                detalles_decoraciones.append(f"Eliminado {clave} en <{tag.name}>")
                continue

            if rgb:
                valor = rgb_to_css(rgb)

            new_styles[clave] = valor

        if new_styles:
            tag['style'] = "; ".join(f"{k}: {v}" for k,v in new_styles.items())
        else:
            del tag['style']


    # Optimización de CSS embebido
    for style_tag in soup.find_all("style"):
        if not style_tag.string:
            continue
        lines = style_tag.string.split("\n")
        new_lines = []
        for line in lines:
            line = ajustar_gradiente_correcto(line, "style embebido", detalles_colores)

            if "rgb(" in line or "#" in line:
                parts = line.split("rgb(")
                for i in range(1, len(parts)):
                    rgb_val = parts[i].split(")")[0]
                    try:
                        rgb = tuple(map(int, rgb_val.split(",")))
                        colores_tot += 1
                        rgb = procesar_rgb(rgb, "style embebido", original_valor=f"rgb({rgb_val})")
                        line = line.replace(f"rgb({rgb_val})", rgb_to_css(rgb))
                    except:
                        continue

                hex_matches = re.findall(r'#(?:[0-9a-fA-F]{3}){1,2}', line)
                for hex_color in hex_matches:
                    rgb = hex_to_rgb(hex_color)
                    if rgb:
                        colores_tot += 1
                        rgb_mod = procesar_rgb(rgb, "style embebido", original_valor=hex_color)
                        line = line.replace(hex_color, rgb_to_css(rgb_mod))

            if any(x in line for x in ["box-shadow", "border", "gradient"]):
                estilos_eliminados += 1
                detalles_decoraciones.append(f"Eliminada decoración en style embebido")
                continue
            new_lines.append(line)
        style_tag.string = "\n".join(new_lines)


    # Optimización de CSS externo
    for link in soup.find_all("link", href=True):
        if link["href"].endswith(".css"):
            ruta_css = os.path.join(base_path, link["href"])
            if os.path.exists(ruta_css):
                with open(ruta_css, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = []
                for line in lines:
                    line = ajustar_gradiente_correcto(line, "CSS externo", detalles_colores)
                    if "rgb(" in line or "#" in line:
                        parts = line.split("rgb(")
                        for i in range(1, len(parts)):
                            rgb_val = parts[i].split(")")[0]
                            try:
                                rgb = tuple(map(int, rgb_val.split(",")))
                                colores_tot += 1
                                rgb = procesar_rgb(rgb, "CSS externo", original_valor=f"rgb({rgb_val})")
                                line = line.replace(f"rgb({rgb_val})", rgb_to_css(rgb))
                            except:
                                continue

                        hex_matches = re.findall(r'#(?:[0-9a-fA-F]{3}){1,2}', line)
                        for hex_color in hex_matches:
                            rgb = hex_to_rgb(hex_color)
                            if rgb:
                                colores_tot += 1
                                rgb_mod = procesar_rgb(rgb, "CSS externo", original_valor=hex_color)
                                line = line.replace(hex_color, rgb_to_css(rgb_mod))

                    if any(x in line for x in ["box-shadow", "border", "gradient"]):
                        estilos_eliminados += 1
                        detalles_decoraciones.append(f"Eliminada decoración en CSS externo")
                        continue
                    new_lines.append(line)
                with open(ruta_css, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)

    for tag in soup.find_all(["link", "img"]):
        attr = "href" if tag.name == "link" else "src"
        if tag.has_attr(attr):
            path = tag[attr]
            clean_path = os.path.normpath(path).replace("\\", "/")
            while clean_path.startswith("../") or clean_path.startswith("./"):
                if clean_path.startswith("../"):
                    clean_path = clean_path[3:]
                elif clean_path.startswith("./"):
                    clean_path = clean_path[2:]
            tag[attr] = clean_path

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

    porcentaje_bril = (colores_bril / colores_tot) * 100 if colores_tot > 0 else 0

    resultados.append({
    "nombre": "Modo oscuro",
    "cumple": not aplicar_dark_mode,
    "recomendacion": "Se aplicó dark mode por fondo claro." if aplicar_dark_mode else "No fue necesario aplicar dark mode."
})

    resultados.append({
        "nombre": "Minimizar el uso de colores brillantes",
        "cumple": porcentaje_bril < 30,
        "recomendacion": f"Se redujo la intensidad de {colores_bril} colores.",
        "detalles": detalles_colores
    })
    resultados.append({
        "nombre": "Reducción de tamaños excesivos",
        "cumple": componentes_grandes == 0,
        "recomendacion": f"Se ajustaron {componentes_grandes} elementos grandes.",
        "detalles": detalles_tamanos
    })
    resultados.append({
        "nombre": "Uso moderado de decoraciones visuales",
        "cumple": estilos_eliminados == 0,
        "recomendacion": f"Se eliminaron {estilos_eliminados} estilos innecesarios.",
        "detalles": detalles_decoraciones
    })

    return resultados
