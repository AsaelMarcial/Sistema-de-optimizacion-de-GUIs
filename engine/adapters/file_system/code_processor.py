from __future__ import annotations

import os
import re
import shutil
from collections import defaultdict

from bs4 import BeautifulSoup

from app.config import get_output_dir
from engine.adapters.color_service import color_registry
from engine.domain.data.css_properties import get_css_property
from engine.domain.data.tokens import PROPERTY_TOKEN_RULES
from engine.domain.utils.color_utils import (
    extract_hex_colors,
    parse_inline_styles,
    reconstruct_inline_style,
)
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.token import TokenInventoryModel
from engine.pipeline.debug_trace import DebugTrace

DEFAULT_ASSET_EXTENSIONS = (
    ".aac",
    ".avif",
    ".bmp",
    ".css",
    ".eot",
    ".gif",
    ".html",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".m4a",
    ".map",
    ".mp3",
    ".mp4",
    ".ogv",
    ".ogg",
    ".otf",
    ".pdf",
    ".png",
    ".svg",
    ".ttf",
    ".txt",
    ".wasm",
    ".wav",
    ".webm",
    ".webmanifest",
    ".webp",
    ".woff",
    ".woff2",
    ".xml",
)
_REMOTE_REFERENCE_PREFIXES = ("http://", "https://", "//", "data:", "javascript:", "mailto:", "tel:")
_HTML_ASSET_ATTRIBUTES = (
    ("a", "href"),
    ("link", "href"),
    ("img", "src"),
    ("script", "src"),
    ("source", "src"),
    ("audio", "src"),
    ("video", "src"),
    ("iframe", "src"),
    ("embed", "src"),
    ("object", "data"),
    ("form", "action"),
)
_SRCSET_ATTRIBUTES = (("img", "srcset"), ("source", "srcset"))
_CSS_URL_REFERENCE_RE = re.compile(r"url\(\s*(['\"]?)([^)'\"]+|[^)]*?)\1\s*\)", re.IGNORECASE)
_COLOR_FRAGMENT_RE = re.compile(
    r"(#[0-9a-fA-F]{3,8}\b|(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\([^)]+\)|\b[a-zA-Z][a-zA-Z-]*\b)",
    re.IGNORECASE,
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


class _TokenRewriteLookup:
    def __init__(
        self,
        *,
        prototype_structure: PrototypeStructure,
    ) -> None:
        self.prototype_structure = prototype_structure

    def element_by_id(self, node_id: str):
        return self.prototype_structure.node_by_id(str(node_id or "").strip())

    def property_by_name(self, node_id: str, property_name: str):
        normalized_node_id = str(node_id or "").strip()
        normalized_property_name = str(property_name or "").strip().lower()
        if not normalized_node_id or not normalized_property_name:
            return None
        return next(
            (
                property_model
                for property_model in self.prototype_structure.properties_for(normalized_node_id)
                if property_model.name == normalized_property_name
            ),
            None,
        )


def reduce_energy_intensity(rgb, factor: float = 0.5):
    r, g, b = rgb
    return (
        int(r + (128 - r) * factor),
        int(g + (128 - g) * factor),
        int(b + (128 - b) * factor),
    )


def is_energy_intensive(rgb) -> bool:
    return max(rgb) > 200 or color_registry.is_light_color(rgb)


def calculate_reduction(before_rgb, after_rgb) -> float:
    initial_luminance = color_registry.luminance(before_rgb)
    transformed_luminance = color_registry.luminance(after_rgb)
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
                details.append(
                    f"{context}: rgb({rgb_value}) -> {color_registry.format_color(adjusted, 'css')} (gradiente)"
                )
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

    parsed_rgb = color_registry.rgb_string_to_tuple(background_value)
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
    return color_registry.variants(value)


def _parseable_color_variants(value: str) -> tuple[str, ...]:
    return color_registry.parseable_variants(value)


def _property_chain(property_name: str) -> tuple[str, ...]:
    normalized = str(property_name or "").strip().lower()
    if not normalized:
        return ()

    chain: list[str] = []
    seen: set[str] = set()
    current = normalized
    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        spec = get_css_property(current)
        if spec is None or spec.longhand_of is None:
            break
        current = spec.longhand_of.value
    return tuple(chain)


def _candidate_declared_properties(
    property_name: str,
    declared_property: str | None = None,
) -> tuple[str, ...]:
    candidates: list[str] = []
    seen: set[str] = set()
    for seed in (declared_property, property_name):
        for candidate in _property_chain(str(seed or "").strip().lower()):
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)
    return tuple(candidates)


def _property_ref_pairs(token) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in token.source_property_refs:
        normalized = str(item or "").strip()
        if not normalized or ":" not in normalized:
            continue
        element_id, property_name = normalized.split(":", 1)
        key = (element_id.strip(), property_name.strip().lower())
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        pairs.append(key)
    return tuple(pairs)


def _matching_color_fragments(
    declaration_value: str,
    target_variants: set[str],
) -> tuple[str, ...]:
    if not target_variants:
        return ()

    matches: list[str] = []
    seen: set[str] = set()
    for candidate in _COLOR_FRAGMENT_RE.findall(str(declaration_value or "")):
        normalized_candidate = str(candidate or "").strip()
        if not normalized_candidate:
            continue
        candidate_variants = set(_parseable_color_variants(normalized_candidate))
        if not candidate_variants or not candidate_variants.intersection(target_variants):
            continue
        lowered = normalized_candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        matches.append(normalized_candidate)
    return tuple(matches)

def _token_source_spec(
    token,
    lookup: _TokenRewriteLookup,
) -> tuple[set[str], set[str], set[str], set[str]]:
    exact_properties = {property_name.lower() for property_name in token.assigned_property_names}
    fragment_properties: set[str] = set()
    exact_values = {
        str(item).strip().lower()
        for item in token.source_values
        if str(item).strip()
    }
    fragment_values = set(exact_values)
    source_color_variants: set[str] = set()

    property_ref_pairs = _property_ref_pairs(token)
    property_refs_by_element: dict[str, set[str]] = defaultdict(set)
    for element_id, property_name in property_ref_pairs:
        property_refs_by_element[element_id].add(property_name)
        exact_properties.add(property_name)
        for candidate in _candidate_declared_properties(property_name):
            if candidate == property_name:
                exact_properties.add(candidate)
            else:
                fragment_properties.add(candidate)

    for source_value in token.source_values:
        source_color_variants.update(_parseable_color_variants(str(source_value)))

    if (token.property_id or "").strip().lower() in {"background-image", "box-shadow", "text-shadow"}:
        fragment_properties.update(exact_properties)
        for source_value in token.source_values:
            for fragment in _COLOR_FRAGMENT_RE.findall(str(source_value or "")):
                fragment_values.update(_parseable_color_variants(fragment))

    candidate_element_ids = {
        str(item).strip()
        for item in (*token.source_element_ids, *token.assigned_element_ids)
        if str(item).strip()
    }
    candidate_element_ids.update(element_id for element_id, _property_name in property_ref_pairs)
    allowed_style_ids = {str(item).strip() for item in token.source_style_ids if str(item).strip()}
    for element_id in candidate_element_ids:
        element_entry = lookup.element_by_id(element_id)
        if element_entry is None:
            continue
        referenced_properties = property_refs_by_element.get(element_id) or exact_properties
        properties_by_name = {
            property_model.name: property_model
            for property_model in lookup.prototype_structure.properties_for(element_entry)
        }
        for property_model in element_entry.properties:
            normalized_property = str(property_model.name or "").strip().lower()
            if normalized_property not in referenced_properties:
                continue
            if allowed_style_ids and property_model.style_id and property_model.style_id not in allowed_style_ids:
                continue
            if property_model.value:
                exact_values.add(str(property_model.value).strip().lower())
                source_color_variants.update(_parseable_color_variants(property_model.value))
            declared_candidates = _candidate_declared_properties(
                normalized_property,
                property_model.declared_property,
            )
            for candidate in declared_candidates:
                if candidate == normalized_property:
                    exact_properties.add(candidate)
                else:
                    fragment_properties.add(candidate)
            resolved_property = properties_by_name.get(normalized_property)
            authored_value = (
                str(resolved_property.authored_value).strip()
                if resolved_property is not None and str(resolved_property.authored_value or "").strip()
                else ""
            )
            if not authored_value:
                continue
            authored_color_fragments = _matching_color_fragments(authored_value, source_color_variants)
            if any(candidate != normalized_property for candidate in declared_candidates):
                fragment_values.update(fragment.lower() for fragment in authored_color_fragments)
            else:
                exact_values.add(authored_value.lower())
                fragment_values.add(authored_value.lower())
                exact_values.update(_color_value_variants(authored_value))

    return exact_properties, fragment_properties, exact_values, fragment_values


def _replace_value_fragments(
    value: str,
    fragment_values: set[str],
    replacement: str,
) -> tuple[str, bool]:
    updated_value = str(value or "")
    changed = False
    for source_value in sorted(fragment_values, key=len, reverse=True):
        if not source_value:
            continue
        updated_value, count = re.subn(
            re.escape(source_value),
            replacement,
            updated_value,
            flags=re.IGNORECASE,
        )
        if count:
            changed = True
    return updated_value, changed


def _split_reference_suffix(value: str) -> tuple[str, str]:
    normalized = str(value or "").strip()
    if not normalized:
        return "", ""
    for marker in ("#", "?"):
        index = normalized.find(marker)
        if index != -1:
            return normalized[:index], normalized[index:]
    return normalized, ""


def _is_remote_reference(value: str) -> bool:
    normalized = str(value or "").strip()
    return not normalized or normalized.startswith(_REMOTE_REFERENCE_PREFIXES) or normalized.startswith("#")


def _resolve_local_reference_path(
    reference: str,
    *,
    current_file_path: str,
    project_base_path: str,
) -> str | None:
    path_value, _suffix = _split_reference_suffix(reference)
    if _is_remote_reference(path_value):
        return None

    normalized_path = path_value.replace("\\", "/")
    if normalized_path.startswith("/"):
        return os.path.normpath(os.path.join(project_base_path, normalized_path.lstrip("/")))

    current_dir = os.path.dirname(current_file_path)
    return os.path.normpath(os.path.join(current_dir, normalized_path))


def _rewrite_local_reference(
    reference: str,
    *,
    current_file_path: str,
    project_base_path: str,
) -> str:
    path_value, suffix = _split_reference_suffix(reference)
    if _is_remote_reference(path_value):
        return str(reference or "")

    normalized_path = path_value.replace("\\", "/")
    if not normalized_path.startswith("/"):
        return f"{normalized_path}{suffix}"

    resolved = _resolve_local_reference_path(
        normalized_path,
        current_file_path=current_file_path,
        project_base_path=project_base_path,
    )
    if not resolved:
        return f"{normalized_path}{suffix}"

    relative_path = os.path.relpath(resolved, os.path.dirname(current_file_path)).replace("\\", "/")
    return f"{relative_path}{suffix}"


def _rewrite_srcset_references(
    value: str,
    *,
    current_file_path: str,
    project_base_path: str,
) -> str:
    candidates = [item.strip() for item in str(value or "").split(",") if item.strip()]
    rewritten: list[str] = []
    for candidate in candidates:
        parts = candidate.split()
        if not parts:
            continue
        asset_reference = _rewrite_local_reference(
            parts[0],
            current_file_path=current_file_path,
            project_base_path=project_base_path,
        )
        if len(parts) > 1:
            rewritten.append(" ".join((asset_reference, *parts[1:])))
        else:
            rewritten.append(asset_reference)
    return ", ".join(rewritten)


def _rewrite_local_asset_attributes(
    soup: BeautifulSoup,
    *,
    current_file_path: str,
    project_base_path: str,
) -> None:
    for tag_name, attribute_name in _HTML_ASSET_ATTRIBUTES:
        for tag in soup.find_all(tag_name):
            if not tag.has_attr(attribute_name):
                continue
            tag[attribute_name] = _rewrite_local_reference(
                str(tag.get(attribute_name) or ""),
                current_file_path=current_file_path,
                project_base_path=project_base_path,
            )
    for tag_name, attribute_name in _SRCSET_ATTRIBUTES:
        for tag in soup.find_all(tag_name):
            if not tag.has_attr(attribute_name):
                continue
            tag[attribute_name] = _rewrite_srcset_references(
                str(tag.get(attribute_name) or ""),
                current_file_path=current_file_path,
                project_base_path=project_base_path,
            )


def _rewrite_css_asset_urls(
    css_text: str,
    *,
    current_file_path: str,
    project_base_path: str,
) -> str:
    def _replace(match: re.Match[str]) -> str:
        quote = match.group(1) or ""
        raw_reference = str(match.group(2) or "").strip()
        if _is_remote_reference(raw_reference):
            return match.group(0)
        rewritten = _rewrite_local_reference(
            raw_reference,
            current_file_path=current_file_path,
            project_base_path=project_base_path,
        )
        return f"url({quote}{rewritten}{quote})"

    return _CSS_URL_REFERENCE_RE.sub(_replace, css_text)


def _build_token_replacement_specs(
    token_inventory: TokenInventoryModel,
    prototype_structure: PrototypeStructure,
) -> list[dict[str, object]]:
    lookup = _TokenRewriteLookup(
        prototype_structure=prototype_structure,
    )
    specs: list[dict[str, object]] = []
    for token in token_inventory:
        if not (token.is_semantic or token.is_component):
            continue
        if not token.assigned_property_names:
            continue
        property_rule = PROPERTY_TOKEN_RULES.get((token.property_id or "").lower())
        if property_rule is not None and not bool(property_rule.get("relevant_for_rewrite", True)):
            continue
        exact_properties, fragment_properties, source_values, fragment_values = _token_source_spec(
            token,
            lookup,
        )
        if not source_values and not fragment_values:
            continue
        replacement = f"var({token.css_variable_name})"
        fragment_mode = (
            "whole_declaration"
            if (token.property_id or "").strip().lower() in {"background-image", "box-shadow", "text-shadow"}
            else "fragment"
        )
        specs.append(
            {
                "token_id": token.token_id,
                "properties": exact_properties,
                "fragment_properties": fragment_properties,
                "tags": set(),
                "source_values": source_values,
                "fragment_values": fragment_values,
                "replacement": replacement,
                "path": token.path_string,
                "fragment_mode": fragment_mode,
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
                replacement = str(spec["replacement"])
                if (
                    normalized_property in spec["properties"]
                    and normalized_value in spec["source_values"]
                ):
                    if styles[property_name] == replacement:
                        break
                    changes.append(
                        f"<{tag.name}> {normalized_property}: {styles[property_name]} -> {replacement} via {spec['path']}"
                    )
                    styles[property_name] = replacement
                    updated = True
                    break
                if normalized_property not in spec["fragment_properties"]:
                    continue
                if str(spec.get("fragment_mode") or "fragment") == "whole_declaration":
                    if not _matching_color_fragments(styles[property_name], set(spec["fragment_values"])):
                        continue
                    if styles[property_name] == replacement:
                        break
                    changes.append(
                        f"<{tag.name}> {normalized_property}: {styles[property_name]} -> {replacement} via {spec['path']}"
                    )
                    styles[property_name] = replacement
                    updated = True
                    break
                rewritten_value, changed = _replace_value_fragments(
                    styles[property_name],
                    set(spec["fragment_values"]),
                    replacement,
                )
                if not changed or rewritten_value == styles[property_name]:
                    continue
                changes.append(
                    f"<{tag.name}> {normalized_property}: {styles[property_name]} -> {rewritten_value} via {spec['path']}"
                )
                styles[property_name] = rewritten_value
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
        for property_name in spec["fragment_properties"]:
            pattern = re.compile(
                rf"({re.escape(str(property_name))}\s*:\s*)([^;}}]+)(\s*[;}}])",
                re.IGNORECASE,
            )

            def _replace(match: re.Match[str]) -> str:
                declaration_value = match.group(2)
                if str(spec.get("fragment_mode") or "fragment") == "whole_declaration":
                    if not _matching_color_fragments(declaration_value, set(spec["fragment_values"])):
                        return match.group(0)
                    if declaration_value == replacement:
                        return match.group(0)
                    changes.append(
                        f"{context_label}: {property_name} -> {replacement} via {spec['path']}"
                    )
                    return f"{match.group(1)}{replacement}{match.group(3)}"
                rewritten_value, changed = _replace_value_fragments(
                    declaration_value,
                    set(spec["fragment_values"]),
                    replacement,
                )
                if not changed or rewritten_value == declaration_value:
                    return match.group(0)
                changes.append(
                    f"{context_label}: {property_name} fragment -> {replacement} via {spec['path']}"
                )
                return f"{match.group(1)}{rewritten_value}{match.group(3)}"

            updated_css = pattern.sub(_replace, updated_css)
    return updated_css, changes


def _token_css_value(token) -> str:
    return token.resolved_value or token.value


def _build_glow_css_variables(
    token_inventory: TokenInventoryModel,
    used_token_ids: set[str] | None = None,
) -> str:
    visible_ids = set(used_token_ids or ())
    ordered_tokens = sorted(
        (
            token
            for token in token_inventory
            if (token.is_semantic or token.is_component)
            and (not visible_ids or token.token_id in visible_ids)
        ),
        key=lambda token: token.path_string,
    )
    lines = [":root {"]
    for token in ordered_tokens:
        css_value = _token_css_value(token)
        if not css_value:
            continue
        lines.append(f"  {token.css_variable_name}: {css_value};")
    lines.append("}")
    return "\n".join(lines)


def _inject_glow_variables(
    soup: BeautifulSoup,
    token_inventory: TokenInventoryModel,
    used_token_ids: set[str] | None = None,
) -> None:
    variable_block = _build_glow_css_variables(token_inventory, used_token_ids)
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
    prototype_structure: PrototypeStructure,
) -> list[dict[str, object]]:
    replacement_specs = _build_token_replacement_specs(
        token_inventory,
        prototype_structure,
    )
    soup = BeautifulSoup(html_content, "html.parser")
    _inject_glow_variables(
        soup,
        token_inventory,
        {str(spec["token_id"]) for spec in replacement_specs},
    )
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
        style_tag.string = _rewrite_css_asset_urls(
            updated_css,
            current_file_path=output_path,
            project_base_path=base_path,
        )
        change_log.extend(css_changes)

    for link in soup.find_all("link", href=True):
        href = link["href"]
        href_path, _href_suffix = _split_reference_suffix(str(href or ""))
        if _is_remote_reference(href_path) or not href_path.lower().endswith(".css"):
            continue
        css_path = _resolve_local_reference_path(
            str(href),
            current_file_path=output_path,
            project_base_path=base_path,
        )
        if not css_path:
            continue
        if not os.path.exists(css_path):
            continue
        with open(css_path, "r", encoding="utf-8") as file:
            css_text = file.read()
        updated_css, css_changes = _apply_token_replacements_to_css_text(
            css_text,
            replacement_specs,
            context_label=f"css_externo:{href}",
        )
        updated_css = _rewrite_css_asset_urls(
            updated_css,
            current_file_path=css_path,
            project_base_path=base_path,
        )
        with open(css_path, "w", encoding="utf-8") as file:
            file.write(updated_css)
        change_log.extend(css_changes)

    _rewrite_local_asset_attributes(
        soup,
        current_file_path=output_path,
        project_base_path=base_path,
    )

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
    aplicar_dark_mode = color_registry.is_light_color(body_bg)

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
                detalles_colores.append(
                    f"{contexto}: {original_valor} → {color_registry.format_color(rgb_mod, 'css')} ({tipo})"
                )
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
                rgb = color_registry.rgb_string_to_tuple(valor)
            elif "#" in valor:
                rgb = color_registry.hex_to_rgb(valor)

            if rgb:
                colores_tot += 1
                if clave == "color" and aplicar_dark_mode:
                    contraste = color_registry.contrast_ratio(rgb, (0, 0, 0))
                    if contraste < 4.5:
                        rgb = color_registry.brighten_color(rgb, 4.5, (0, 0, 0))
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
                valor = color_registry.format_color(rgb, "css")

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
                        line = line.replace(f"rgb({rgb_val})", color_registry.format_color(rgb, "css"))
                    except ValueError:
                        continue

                for hex_color in extract_hex_colors(line):
                    rgb = color_registry.hex_to_rgb(hex_color)
                    if rgb:
                        colores_tot += 1
                        rgb_mod = procesar_rgb(rgb, "style embebido", original_valor=hex_color)
                        line = line.replace(hex_color, color_registry.format_color(rgb_mod, "css"))

            if any(x in line for x in ["box-shadow", "border", "gradient"]):
                estilos_eliminados += 1
                detalles_decoraciones.append("Eliminada decoración en style embebido")
                continue
            new_lines.append(line)
        style_tag.string = _rewrite_css_asset_urls(
            "\n".join(new_lines),
            current_file_path=output_path,
            project_base_path=base_path,
        )

    # 5) Transformación de CSS externo referenciado por <link>
    for link in soup.find_all("link", href=True):
        href = link["href"]
        href_path, _href_suffix = _split_reference_suffix(str(href or ""))
        if _is_remote_reference(href_path):
            continue
        if href_path.lower().endswith(".css"):
            ruta_css = _resolve_local_reference_path(
                str(href),
                current_file_path=output_path,
                project_base_path=base_path,
            )
            if not ruta_css:
                continue
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
                                line = line.replace(
                                    f"rgb({rgb_val})",
                                    color_registry.format_color(rgb, "css"),
                                )
                            except ValueError:
                                continue

                        for hex_color in extract_hex_colors(line):
                            rgb = color_registry.hex_to_rgb(hex_color)
                            if rgb:
                                colores_tot += 1
                                rgb_mod = procesar_rgb(rgb, "CSS externo", original_valor=hex_color)
                                line = line.replace(hex_color, color_registry.format_color(rgb_mod, "css"))

                    if any(x in line for x in ["box-shadow", "border", "gradient"]):
                        estilos_eliminados += 1
                        detalles_decoraciones.append("Eliminada decoración en CSS externo")
                        continue
                    new_lines.append(line)
                updated_css = _rewrite_css_asset_urls(
                    "".join(new_lines),
                    current_file_path=ruta_css,
                    project_base_path=base_path,
                )
                with open(ruta_css, "w", encoding="utf-8") as file:
                    file.write(updated_css)

    _rewrite_local_asset_attributes(
        soup,
        current_file_path=output_path,
        project_base_path=base_path,
    )

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

