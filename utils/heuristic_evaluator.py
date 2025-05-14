import os
from bs4 import BeautifulSoup

def intensidad(rgb):
    R, G, B = rgb
    return 0.299 * R + 0.587 * G + 0.114 * B

def rgb_string_to_tuple(color_str):
    color_str = color_str.strip().lower().replace("rgb(", "").replace(")", "")
    try:
        return tuple(map(int, color_str.split(",")))
    except:
        return None

def oscurecer_rgb(rgb):
    return tuple(max(c // 2, 0) for c in rgb)

def evaluar_y_corregir_heuristicas(html_content, output_path, base_path):
    soup = BeautifulSoup(html_content, "html.parser")
    resultados = []

    colores_bril = 0
    colores_tot = 0
    componentes_grandes = 0
    estilos_eliminados = 0

    # ✅ Estilos inline (atributo style)
    for tag in soup.find_all(style=True):
        style = tag['style']
        nuevo_style = []
        for prop in style.split(";"):
            if ":" not in prop:
                continue
            clave, valor = prop.split(":", 1)
            clave = clave.strip().lower()
            valor = valor.strip()

            rgb_clean = valor.replace(" ", "")
            rgb = rgb_string_to_tuple(rgb_clean) if "rgb(" in rgb_clean else None

            if rgb:
                colores_tot += 1
                if any(c > 180 for c in rgb):  # ✔️ cambio importante aquí
                    colores_bril += 1
                    nuevo_rgb = oscurecer_rgb(rgb)
                    valor = f"rgb({nuevo_rgb[0]},{nuevo_rgb[1]},{nuevo_rgb[2]})"

            if "width" in clave or "height" in clave:
                try:
                    val = int(valor.replace("px", "").strip())
                    if val > 500:
                        val = 400 if "width" in clave else 300
                        valor = f"{val}px"
                        componentes_grandes += 1
                except:
                    pass

            if any(x in clave for x in ["box-shadow", "border", "gradient"]):
                estilos_eliminados += 1
                continue

            nuevo_style.append(f"{clave}: {valor}")
        tag['style'] = "; ".join(nuevo_style)
        print(f"🎨 Estilo modificado en <{tag.name}>: {tag['style']}")


    # ✅ Estilos embebidos dentro de <style>
    for style_tag in soup.find_all("style"):
        css_lines = style_tag.string.split("\\n") if style_tag.string else []
        new_lines = []
        for line in css_lines:
            if "rgb(" in line:
                parts = line.split("rgb(")
                for i in range(1, len(parts)):
                    rgb_val = parts[i].split(")")[0]
                    try:
                        rgb = tuple(map(int, rgb_val.split(",")))
                        if any(c > 180 for c in rgb):
                            oscuro = oscurecer_rgb(rgb)
                            line = line.replace(
                                f"rgb({rgb_val})",
                                f"rgb({oscuro[0]},{oscuro[1]},{oscuro[2]})"
                            )
                    except:
                        continue
            if any(x in line for x in ["box-shadow", "border", "gradient"]):
                estilos_eliminados += 1
                continue
            new_lines.append(line)
        style_tag.string = "\\n".join(new_lines)

    # ✅ Corrección de rutas en <link> y <img>
    for tag in soup.find_all(["link", "img"]):
        attr = "href" if tag.name == "link" else "src"
        if tag.has_attr(attr):
            path = tag[attr]
            if path.startswith("../"):
                tag[attr] = path.replace("../", "")
            elif path.startswith("./"):
                tag[attr] = path.replace("./", "")

    # ✅ Modificación de archivos CSS externos
    for link in soup.find_all("link", href=True):
        if link["href"].endswith(".css"):
            ruta_css = os.path.join(base_path, link["href"])
            if os.path.exists(ruta_css):
                try:
                    with open(ruta_css, "r", encoding="utf-8") as f:
                        css_lines = f.readlines()

                    new_lines = []
                    for line in css_lines:
                        if "rgb(" in line:
                            parts = line.split("rgb(")
                            for i in range(1, len(parts)):
                                rgb_val = parts[i].split(")")[0]
                                try:
                                    rgb = tuple(map(int, rgb_val.split(",")))
                                    if intensidad(rgb) > 128:
                                        oscuro = oscurecer_rgb(rgb)
                                        line = line.replace(
                                            f"rgb({rgb_val})",
                                            f"rgb({oscuro[0]},{oscuro[1]},{oscuro[2]})"
                                        )
                                except:
                                    continue
                        if any(x in line for x in ["box-shadow", "border", "gradient"]):
                            estilos_eliminados += 1
                            continue
                        new_lines.append(line)

                    with open(ruta_css, "w", encoding="utf-8") as f:
                        f.writelines(new_lines)

                except Exception as e:
                    print(f"Error procesando CSS: {e}")
    # ✅ Guardar HTML corregido en el archivo original
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(str(soup))
        print("✅ Guardando HTML corregido en:", output_path)


    # ✅ Registrar resultados de la heurística
    porcentaje_bril = (colores_bril / colores_tot) * 100 if colores_tot > 0 else 0

    resultados.append({
        "nombre": "Modo oscuro por defecto",
        "cumple": porcentaje_bril < 30,
        "recomendacion": "Se oscurecieron varios colores brillantes." if porcentaje_bril >= 30 else "La mayoría de los colores ya eran oscuros."
    })

    resultados.append({
        "nombre": "Reducir tamaños excesivos",
        "cumple": componentes_grandes == 0,
        "recomendacion": f"Se ajustaron {componentes_grandes} elementos con tamaños excesivos." if componentes_grandes else "No se encontraron elementos excesivamente grandes."
    })

    resultados.append({
        "nombre": "Eliminar bordes, sombras y gradientes decorativos",
        "cumple": estilos_eliminados == 0,
        "recomendacion": f"Se eliminaron {estilos_eliminados} estilos decorativos innecesarios." if estilos_eliminados else "No se encontraron estilos decorativos complejos."
    })

    return resultados
