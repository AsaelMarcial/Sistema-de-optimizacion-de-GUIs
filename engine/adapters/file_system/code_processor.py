from __future__ import annotations

import os
import re
import shutil
from collections import defaultdict

from bs4 import BeautifulSoup

from app.config import get_output_dir
from engine.domain.data.tokens import PROPERTY_TOKEN_RULES
from engine.domain.utils.color_utils import (
    extract_hex_colors,
    parse_inline_styles,
    reconstruct_inline_style,
)
from engine.domain.models.inventory_graph import InventoryGraphModel
from engine.domain.models.token import TokenInventoryModel
from engine.domain.utils.coloraide import (
    brighten_color,
    color_to_hex,
    color_to_rgb_tuple,
    contrast_ratio,
    hex_to_rgb,
    is_light_color,
    luminance,
    rgb_string_to_tuple,
    rgb_to_css,
)
from engine.pipeline.debug_trace import DebugTrace

DEFAULT_ASSET_EXTENSIONS = (
    ".css",
    ".gif",
    ".html",
    ".jpeg",
    ".jpg",
    ".js",
    ".png",
    ".svg",
    ".webp",
)


def stage_project_assets(
    input_dir: str,
    output_dir: str,
    allowed_extensions: tuple[str, ...] = DEFAULT_ASSET_EXTENSIONS,
) -> None:
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if not filename.lower().endswith(allowed_extensions):
                continue

            source_path = os.path.join(root, filename)
            relative_path = os.path.relpath(source_path, input_dir)
            target_path = os.path.join(output_dir, relative_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(source_path, target_path)


def load_transformed_html(transformed_html_path: str) -> tuple[str, str]:
    with open(transformed_html_path, "r", encoding="utf-8") as file:
        transformed_html_content = file.read()
    return transformed_html_path, transformed_html_content

trace = DebugTrace(enabled=True)
_DECLARATION_PATTERN_TEMPLATE = r"({property}\s*:\s*){value}(\s*[;}}])"


def reduce_energy_intensity(rgb, factor: float = 0.5):
    r, g, b = rgb
    return (
        int(r + (128 - r) * factor),
        int(g + (128 - g) * factor),
        int(b + (128 - b) * factor),
    )


def is_energy_intensive(rgb) -> bool:
    return max(rgb) > 200 or is_light_color(rgb)


def calculate_reduction(before_rgb, after_rgb) -> float:
    initial_luminance = luminance(before_rgb)
    transformed_luminance = luminance(after_rgb)
    if initial_luminance == 0:
        return 0.0
    reduction = ((initial_luminance - transformed_luminance) / initial_luminance) * 100
    return round(reduction, 2)


def adjust_gradient_rgb_line(line: str, context: str, details: list[str] | None = None) -> str:
    if "linear-gradient" not in line or "rgb(" not in line:
        return line

    parts = line.split("rgb(")
    rebuilt = [parts[0]]
    for index in range(1, len(parts)):
        rgb_value = parts[index].split(")")[0]
        try:
            rgb = tuple(map(int, rgb_value.split(",")))
        except ValueError:
            rebuilt.append("rgb(" + parts[index])
            continue

        if is_energy_intensive(rgb):
            factor = 0.5 if max(rgb) > 240 else 0.3
            adjusted = reduce_energy_intensity(rgb, factor=factor)
            rebuilt.append(f"{adjusted[0]},{adjusted[1]},{adjusted[2]})".join(parts[index].split(")", 1)))
            if details is not None:
                details.append(f"{context}: rgb({rgb_value}) -> {rgb_to_css(adjusted)} (gradiente)")
        else:
            rebuilt.append("rgb(" + parts[index])

    return "".join(rebuilt)


def detect_body_background_rgb(soup) -> tuple[int, int, int]:
    body = soup.find("body")
    if not body or "style" not in body.attrs:
        return (255, 255, 255)

    styles = parse_inline_styles(body["style"])
    background_value = styles.get("background-color")
    if not background_value:
        return (255, 255, 255)

    parsed_rgb = rgb_string_to_tuple(background_value)
    return parsed_rgb if parsed_rgb else (255, 255, 255)


def build_heuristics_results(environmental_components):
    heuristics_dict = defaultdict(lambda: {"detalles": [], "comparativas": []})

    for component in environmental_components:
        ahorro = calculate_reduction(component["before_rgb"], component["after_rgb"])

        heuristics_dict[component["heuristic"]]["comparativas"].append(
            {
                "nombre": component["nombre"],
                "antes": f"{component['before_rgb'][0]}, {component['before_rgb'][1]}, {component['before_rgb'][2]}",
                "despues": f"{component['after_rgb'][0]}, {component['after_rgb'][1]}, {component['after_rgb'][2]}",
                "ahorro": ahorro,
            }
        )

    heuristics_results = []
    for heuristic_name, data in heuristics_dict.items():
        detalles = [
            (
                f"{component['nombre']}: color antes RGB({component['antes']}) -> despues RGB({component['despues']}) | "
                f"Ahorro estimado: {component['ahorro']}%"
            )
            for component in data["comparativas"]
        ]
        heuristics_results.append(
            {
                "nombre": heuristic_name,
                "cumple": True,
                "recomendacion": (
                    f"Se han transformado {len(data['comparativas'])} componentes bajo la heuristica "
                    f"'{heuristic_name}'."
                ),
                "detalles": detalles,
                "comparativas": data["comparativas"],
            }
        )

    return heuristics_results


def _color_value_variants(value: str) -> tuple[str, ...]:
    normalized = str(value or "").strip()
    if not normalized:
        return ()
    variants = {normalized.lower()}
    try:
        variants.add(color_to_hex(normalized).lower())
        variants.add(rgb_to_css(color_to_rgb_tuple(normalized)).lower())
    except Exception:
        pass
    return tuple(sorted(variants))


def _build_token_replacement_specs(
    token_inventory: TokenInventoryModel,
    inventory_graph: InventoryGraphModel,
) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    for token in token_inventory:
        if not (token.is_semantic or token.is_component):
            continue
        if not token.assigned_property_names:
            continue
        property_rule = PROPERTY_TOKEN_RULES.get((token.property_id or "").lower())
        if property_rule is not None and not bool(property_rule.get("relevant_for_rewrite", True)):
            continue
        source_values: set[str] = set()
        source_values.update(str(item).strip().lower() for item in token.source_values if str(item).strip())
        for color_id in token.source_color_ids:
            color_entry = inventory_graph.color_by_id(color_id)
            if color_entry is None:
                continue
            source_values.update(_color_value_variants(color_entry.value))
            source_values.update(_color_value_variants(color_entry.hex_value))
            source_values.update(_color_value_variants(rgb_to_css(color_entry.rgb)))
        if not source_values:
            continue
        replacement = f"var({token.css_variable_name})"
        specs.append(
            {
                "token_id": token.token_id,
                "properties": {property_name.lower() for property_name in token.assigned_property_names},
                "tags": set(),
                "source_values": source_values,
                "replacement": replacement,
                "path": token.path_string,
            }
        )
    return specs


def _apply_inline_token_replacements(
    soup: BeautifulSoup,
    replacement_specs: list[dict[str, object]],
) -> list[str]:
    changes: list[str] = []
    for tag in soup.find_all(style=True):
        styles = parse_inline_styles(tag["style"])
        updated = False
        for property_name, value in list(styles.items()):
            normalized_property = property_name.strip().lower()
            normalized_value = str(value or "").strip().lower()
            for spec in replacement_specs:
                tags = spec["tags"]
                if tags and tag.name.lower() not in tags:
                    continue
                if normalized_property not in spec["properties"]:
                    continue
                if normalized_value not in spec["source_values"]:
                    continue
                replacement = str(spec["replacement"])
                if styles[property_name] == replacement:
                    break
                changes.append(
                    f"<{tag.name}> {normalized_property}: {styles[property_name]} -> {replacement} via {spec['path']}"
                )
                styles[property_name] = replacement
                updated = True
                break
        if updated:
            tag["style"] = reconstruct_inline_style(styles)
    return changes


def _apply_token_replacements_to_css_text(
    css_text: str,
    replacement_specs: list[dict[str, object]],
    *,
    context_label: str,
) -> tuple[str, list[str]]:
    updated_css = css_text
    changes: list[str] = []
    for spec in replacement_specs:
        replacement = str(spec["replacement"])
        for property_name in spec["properties"]:
            for source_value in spec["source_values"]:
                pattern = re.compile(
                    _DECLARATION_PATTERN_TEMPLATE.format(
                        property=re.escape(str(property_name)),
                        value=re.escape(str(source_value)),
                    ),
                    re.IGNORECASE,
                )
                updated_css, count = pattern.subn(rf"\1{replacement}\2", updated_css)
                if count:
                    changes.append(
                        f"{context_label}: {property_name} {source_value} -> {replacement} via {spec['path']} ({count})"
                    )
    return updated_css, changes


def _token_css_value(token) -> str:
    if token.alias_to:
        alias_var = "--" + token.alias_to.replace(".", "-").replace("_", "-")
        return f"var({alias_var})"
    return token.resolved_value or token.value


def _build_glow_css_variables(token_inventory: TokenInventoryModel) -> str:
    ordered_tokens = sorted(
        token_inventory,
        key=lambda token: (0 if token.is_foundation else 1, token.path_string),
    )
    lines = [":root {"]
    for token in ordered_tokens:
        css_value = _token_css_value(token)
        if not css_value:
            continue
        lines.append(f"  {token.css_variable_name}: {css_value};")
    lines.append("}")
    return "\n".join(lines)


def _inject_glow_variables(soup: BeautifulSoup, token_inventory: TokenInventoryModel) -> None:
    variable_block = _build_glow_css_variables(token_inventory)
    if variable_block.strip() == ":root {\n}":
        return
    head = soup.head
    if head is None:
        head = soup.new_tag("head")
        if soup.html is not None:
            soup.html.insert(0, head)
        else:
            soup.insert(0, head)
    existing = soup.find("style", attrs={"data-glow-tokens": "true"})
    if existing is not None:
        existing.string = variable_block
        return
    style_tag = soup.new_tag("style")
    style_tag["data-glow-tokens"] = "true"
    style_tag.string = variable_block
    head.insert(0, style_tag)


def apply_tokens_to_project(
    html_content: str,
    output_path: str,
    base_path: str,
    token_inventory: TokenInventoryModel,
    inventory_graph: InventoryGraphModel,
) -> list[dict[str, object]]:
    replacement_specs = _build_token_replacement_specs(token_inventory, inventory_graph)
    soup = BeautifulSoup(html_content, "html.parser")
    _inject_glow_variables(soup, token_inventory)
    change_log = _apply_inline_token_replacements(soup, replacement_specs)

    for style_tag in soup.find_all("style"):
        css_text = style_tag.string or ""
        if not css_text.strip():
            continue
        updated_css, css_changes = _apply_token_replacements_to_css_text(
            css_text,
            replacement_specs,
            context_label="style_embebido",
        )
        style_tag.string = updated_css
        change_log.extend(css_changes)

    for link in soup.find_all("link", href=True):
        href = link["href"]
        if href.startswith(("http://", "https://", "//")) or not href.endswith(".css"):
            continue
        css_path = os.path.join(base_path, href.lstrip("/"))
        if not os.path.exists(css_path):
            continue
        with open(css_path, "r", encoding="utf-8") as file:
            css_text = file.read()
        updated_css, css_changes = _apply_token_replacements_to_css_text(
            css_text,
            replacement_specs,
            context_label=f"css_externo:{href}",
        )
        with open(css_path, "w", encoding="utf-8") as file:
            file.write(updated_css)
        change_log.extend(css_changes)

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

    if not replacement_specs:
        return []

    if not change_log:
        return []

    trace.add_step(
        "transformed.tokens_applied",
        {
            "changes": change_log,
        },
    )
    return [
        {
            "nombre": "Token-driven color transformation",
            "cumple": True,
            "recomendacion": f"Se aplicaron {len(change_log)} reemplazos guiados por tokens.",
            "detalles": change_log,
        }
    ]


def evaluate_and_apply_heuristics(html_content, output_path, base_path, session_id):

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

