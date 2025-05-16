import os
from bs4 import BeautifulSoup
from utils.color_utils import parse_rgb, rgb_to_css, is_light_color, contrast_ratio, brighten_color
from utils.evaluation_metrics import build_heuristics_results

def rgb_string_to_tuple(color_str):
    color_str = color_str.strip().lower().replace("rgb(", "").replace(")", "")
    try:
        return tuple(map(int, color_str.split(",")))
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

def ajustar_gradiente_correcto(linea, contexto, detalles_colores, optimized_components):
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
                    detalles_colores.append(f"Gradiente en {contexto}: {rgb} → {rgb_mod}")
                    optimized_components.append({
                        'heuristic': 'Reducción de gradientes',
                        'nombre': f"Gradiente ({contexto})",
                        'before_rgb': rgb,
                        'after_rgb': rgb_mod
                    })
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
    soup = BeautifulSoup(html_content, "html.parser")
    resultados = []
    detalles_colores = []
    detalles_tamanos = []
    detalles_decoraciones = []
    optimized_components = []

    colores_bril = 0
    colores_tot = 0
    componentes_grandes = 0
    estilos_eliminados = 0

    body_bg = detectar_fondo_body(soup)
    aplicar_dark_mode = is_light_color(body_bg)

    if aplicar_dark_mode:
        body = soup.find('body')
        if body:
            optimized_components.append({
                'heuristic': 'Priorizar colores oscuros',
                'nombre': 'Body Background',
                'before_rgb': body_bg,
                'after_rgb': (0, 0, 0)
            })
            body['style'] = f"background-color: rgb(0,0,0)"

    def procesar_rgb(rgb, contexto, tag_name):
        nonlocal colores_bril
        if is_energy_intensive(rgb):
            new_rgb = reduce_energy_intensity(rgb, factor=0.5)
            colores_bril += 1
            detalles_colores.append(f"Se redujo intensidad de {contexto} color {rgb}")
            optimized_components.append({
                'heuristic': 'Reducir colores brillantes',
                'nombre': f"{tag_name} ({contexto})",
                'before_rgb': rgb,
                'after_rgb': new_rgb
            })
            return new_rgb
        return rgb

    # Inline styles
    for tag in soup.find_all(style=True):
        styles = {k.strip(): v.strip() for k,v in [x.split(":") for x in tag['style'].split(";") if ":" in x]}
        new_styles = {}

        for clave, valor in styles.items():
            rgb = rgb_string_to_tuple(valor) if "rgb(" in valor else None

            if rgb:
                colores_tot += 1
                if clave == 'color' and aplicar_dark_mode:
                    contrast = contrast_ratio(rgb, (0, 0, 0))
                    if contrast < 4.5:
                        new_rgb = brighten_color(rgb, 4.5, (0, 0, 0))
                        optimized_components.append({
                            'heuristic': 'Ajuste de contraste',
                            'nombre': f"{tag.name} (texto)",
                            'before_rgb': rgb,
                            'after_rgb': new_rgb
                        })
                        rgb = new_rgb
                elif 'background' in clave:
                    rgb = procesar_rgb(rgb, f"<{tag.name}>", tag.name)

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

    # Styles embebidos
    for style_tag in soup.find_all("style"):
            if not style_tag.string:
                continue
            lines = style_tag.string.split("\n")
            new_lines = []
            for line in lines:
                line = ajustar_gradiente_correcto(line, "style embebido", detalles_colores, optimized_components)
                if "rgb(" in line:
                    parts = line.split("rgb(")
                    new_line = parts[0]
                    for i in range(1, len(parts)):
                        rgb_val = parts[i].split(")")[0]
                        try:
                            rgb = tuple(map(int, rgb_val.split(",")))
                            colores_tot += 1
                            new_rgb = procesar_rgb(rgb, "style embebido", "style")
                            line = line.replace(f"rgb({rgb_val})", rgb_to_css(new_rgb))
                        except:
                            continue
                if any(x in line for x in ["box-shadow", "border", "gradient"]):
                    estilos_eliminados += 1
                    detalles_decoraciones.append(f"Eliminada decoración en style embebido")
                    continue
                new_lines.append(line)
            style_tag.string = "\n".join(new_lines)

    # CSS externos
    for link in soup.find_all("link", href=True):
        if link["href"].endswith(".css"):
            ruta_css = os.path.join(base_path, link["href"])
            if os.path.exists(ruta_css):
                with open(ruta_css, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                new_lines = []
                for line in lines:
                    line = ajustar_gradiente_correcto(line, "CSS externo", detalles_colores, optimized_components)
                    if "rgb(" in line:
                        parts = line.split("rgb(")
                        for i in range(1, len(parts)):
                            rgb_val = parts[i].split(")")[0]
                            try:
                                rgb = tuple(map(int, rgb_val.split(",")))
                                colores_tot += 1
                                new_rgb = procesar_rgb(rgb, "CSS externo", "css")
                                line = line.replace(f"rgb({rgb_val})", rgb_to_css(new_rgb))
                            except:
                                continue
                    if any(x in line for x in ["box-shadow", "border", "gradient"]):
                        estilos_eliminados += 1
                        detalles_decoraciones.append(f"Eliminada decoración en CSS externo")
                        continue
                    new_lines.append(line)
                with open(ruta_css, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)

    porcentaje_bril = (colores_bril / colores_tot) * 100 if colores_tot > 0 else 0

    resultados.append({
        "nombre": "Optimización de colores y contraste",
        "cumple": aplicar_dark_mode and porcentaje_bril < 30,
        "recomendacion": "Se aplicó modo oscuro y se redujeron colores brillantes y contrastes.",
        "detalles": detalles_colores
    })
    resultados.append({
        "nombre": "Reducción de decoraciones visuales",
        "cumple": estilos_eliminados == 0,
        "recomendacion": f"Se eliminaron {estilos_eliminados} estilos innecesarios.",
        "detalles": detalles_decoraciones
    })
    resultados.append({
        "nombre": "Reducción de tamaños excesivos",
        "cumple": componentes_grandes == 0,
        "recomendacion": f"Se ajustaron {componentes_grandes} elementos grandes.",
        "detalles": detalles_tamanos
    })

    comparativas = build_heuristics_results(optimized_components)

    # Integrar comparativas en las heurísticas agrupadas
    for heuristica in resultados:
        if heuristica['nombre'] == "Optimización de colores y contraste":
            heuristica['comparativas'] = []
            for comp in comparativas:
                if comp['nombre'] in ['Priorizar colores oscuros', 'Reducir colores brillantes', 'Ajuste de contraste']:
                    heuristica['comparativas'].extend(comp['comparativas'])
        elif heuristica['nombre'] == "Reducción de decoraciones visuales":
            heuristica['comparativas'] = []
            for comp in comparativas:
                if comp['nombre'] == 'Reducción de gradientes':
                    heuristica['comparativas'].extend(comp['comparativas'])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(soup))

    return resultados

