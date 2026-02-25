import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from playwright.sync_api import Page, sync_playwright

from engine.rendering.utils.screenshot_utils import remove_temp_html, write_temp_html


@dataclass
class SnapshotOptions:
    wait_after_load_ms: int = 500
    include_invisible: bool = True
    exclude_user_agent_rules: bool = True


COLOR_PROP_TO_CSS_NAME = {
    "color": "color",
    "currentColor": "color",
    "backgroundColor": "background-color",
    "textShadow": "text-shadow",
    "textDecorationColor": "text-decoration-color",
    "textEmphasisColor": "text-emphasis-color",
    "caretColor": "caret-color",
    "borderColor": "border-color",
    "borderLeftColor": "border-left-color",
    "borderRightColor": "border-right-color",
    "borderTopColor": "border-top-color",
    "borderBottomColor": "border-bottom-color",
    "borderBlockStartColor": "border-block-start-color",
    "borderBlockEndColor": "border-block-end-color",
    "borderInlineStartColor": "border-inline-start-color",
    "boxShadow": "box-shadow",
    "columnRuleColor": "column-rule-color",
    "outlineColor": "outline-color",
}


EXCLUDED_TAGS = {
    # Embedded/media
    "AUDIO",
    "VIDEO",
    "IMG",
    "PICTURE",
    "SVG",
    "CANVAS",
    "IFRAME",
    "EMBED",
    "OBJECT",
    "PARAM",
    "SOURCE",
    "TRACK",
    "MAP",
    "AREA",
    # Math/Scripting
    "MATH",
    "SCRIPT",
    "NOSCRIPT",
    # Edits/demarcation
    "DEL",
    "INS",
    # Web Components asked to exclude
    "SLOT",
    "TEMPLATE",
    # Obsolete/deprecated common set
    "APPLET",
    "BASEFONT",
    "BIG",
    "CENTER",
    "DIR",
    "FONT",
    "FRAME",
    "FRAMESET",
    "MARQUEE",
    "NOFRAMES",
    "STRIKE",
    "TT",
    "XMP",
}


def _build_dom_probe_js() -> str:
    return """
    () => {
      const SKIP_TAGS = new Set(%s);

      const toPath = (el) => {
        if (!(el instanceof Element)) return '';
        const segments = [];
        let node = el;
        while (node && node.nodeType === Node.ELEMENT_NODE) {
          const tag = node.tagName.toLowerCase();
          const parent = node.parentElement;
          if (!parent) {
            segments.unshift(tag);
            break;
          }
          const siblings = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
          const index = siblings.indexOf(node) + 1;
          segments.unshift(`${tag}:nth-of-type(${index})`);
          node = parent;
        }
        return segments.join(' > ');
      };

      const parsePx = (value) => {
        const n = parseFloat(value || '0');
        return Number.isFinite(n) ? n : 0;
      };

      const shouldInclude = (el) => {
        if (!(el instanceof Element)) return false;
        if (el.tagName === 'HTML' || el.tagName === 'BODY') return true;
        if (!document.body || !document.body.contains(el)) return false;
        if (SKIP_TAGS.has(el.tagName)) return false;
        return true;
      };

      const styleOf = (el) => window.getComputedStyle(el);
      const nodes = [];
      const all = Array.from(document.querySelectorAll('*')).filter(shouldInclude);

      for (const el of all) {
        const style = styleOf(el);
        const rect = el.getBoundingClientRect();
        const visible = !(
          style.display === 'none' ||
          style.visibility === 'hidden' ||
          parseFloat(style.opacity || '1') === 0 ||
          (rect.width === 0 && rect.height === 0)
        );

        nodes.push({
          domPath: toPath(el),
          tag: el.tagName,
          depth: (() => {
            let d = 0;
            let cur = el.parentElement;
            while (cur) { d += 1; cur = cur.parentElement; }
            return d;
          })(),
          layout: {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
            zIndex: style.zIndex,
          },
          boxes: {
            margin: {
              top: parsePx(style.marginTop),
              right: parsePx(style.marginRight),
              bottom: parsePx(style.marginBottom),
              left: parsePx(style.marginLeft),
            },
            padding: {
              top: parsePx(style.paddingTop),
              right: parsePx(style.paddingRight),
              bottom: parsePx(style.paddingBottom),
              left: parsePx(style.paddingLeft),
            },
            borderWidth: {
              top: parsePx(style.borderTopWidth),
              right: parsePx(style.borderRightWidth),
              bottom: parsePx(style.borderBottomWidth),
              left: parsePx(style.borderLeftWidth),
            },
          },
          computedColors: {
            color: style.color,
            currentColor: style.color,
            backgroundColor: style.backgroundColor,
            textShadow: style.textShadow,
            textDecorationColor: style.textDecorationColor,
            textEmphasisColor: style.textEmphasisColor,
            caretColor: style.caretColor,
            borderColor: style.borderColor,
            borderLeftColor: style.borderLeftColor,
            borderRightColor: style.borderRightColor,
            borderTopColor: style.borderTopColor,
            borderBottomColor: style.borderBottomColor,
            borderBlockStartColor: style.borderBlockStartColor,
            borderBlockEndColor: style.borderBlockEndColor,
            borderInlineStartColor: style.borderInlineStartColor,
            boxShadow: style.boxShadow,
            columnRuleColor: style.columnRuleColor,
            outlineColor: style.outlineColor,
          },
          renderState: {
            display: style.display,
            visibility: style.visibility,
            opacity: style.opacity,
            pointerEvents: style.pointerEvents,
          },
          visible,
        });
      }

      return {
        url: window.location.href,
        viewport: { width: window.innerWidth, height: window.innerHeight },
        documentSize: {
          width: Math.max(document.body?.scrollWidth || 0, document.documentElement?.scrollWidth || 0),
          height: Math.max(document.body?.scrollHeight || 0, document.documentElement?.scrollHeight || 0),
        },
        nodes,
      };
    }
    """ % json.dumps(sorted(EXCLUDED_TAGS))


def _extract_declared_property_names(style_obj: Dict[str, Any]) -> Set[str]:
    names: Set[str] = set()
    for prop in style_obj.get("cssProperties", []) or []:
        name = prop.get("name")
        value = prop.get("value")
        if name and value not in (None, ""):
            names.add(name)
    return names


def _extract_rule_declarations(style_obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    declarations: List[Dict[str, Any]] = []
    for prop in style_obj.get("cssProperties", []) or []:
        name = prop.get("name")
        value = prop.get("value")
        if not name or value in (None, ""):
            continue
        declarations.append(
            {
                "name": name,
                "value": value,
                "important": prop.get("important", False),
                "implicit": prop.get("implicit", False),
                "text": prop.get("text"),
            }
        )
    return declarations


def _summarize_selector_list(rule: Dict[str, Any]) -> Dict[str, Any]:
    selector_list = rule.get("selectorList", {})
    selectors = []
    for sel in selector_list.get("selectors", []) or []:
        specificity = sel.get("specificity") or {}
        selectors.append(
            {
                "text": sel.get("text"),
                "range": sel.get("range"),
                "specificity": {
                    "idSelectors": specificity.get("a", 0),
                    "classAttributePseudoClassSelectors": specificity.get("b", 0),
                    "typeAndPseudoElementSelectors": specificity.get("c", 0),
                },
            }
        )
    return {
        "text": selector_list.get("text"),
        "selectors": selectors or None,
    }


def _summarize_rule_match(rule_entry: Dict[str, Any]) -> Dict[str, Any]:
    rule = rule_entry.get("rule", {})
    style = rule.get("style", {})
    selector_list = _summarize_selector_list(rule)
    matching_indexes = rule_entry.get("matchingSelectors", [])
    matching_texts = []
    selectors = selector_list.get("selectors", [])
    for idx in matching_indexes:
        if isinstance(idx, int) and 0 <= idx < len(selectors):
            txt = selectors[idx].get("text")
            if txt:
                matching_texts.append(txt)

    return {
        "matchingSelectors": matching_indexes or None,
        "matchingSelectorTexts": matching_texts or None,
        "origin": rule.get("origin"),
        "originDescription": {
            "regular": "Regla de stylesheet de autor (author stylesheet).",
            "user-agent": "Regla por defecto del navegador (user agent stylesheet).",
            "injected": "Regla inyectada dinámicamente por DevTools o runtime.",
            "inspector": "Regla creada/forzada desde inspector.",
        }.get(rule.get("origin"), "Origen no clasificado."),
        "styleSheetId": style.get("styleSheetId"),
        "styleSheet": None,
        "range": style.get("range"),
        "selectorList": selector_list,
        "declarations": _extract_rule_declarations(style),
    }


def _rule_entry_allowed(rule_entry: Dict[str, Any], *, exclude_user_agent_rules: bool) -> bool:
    match_indexes = rule_entry.get("matchingSelectors", []) or []
    if not match_indexes:
        return False
    origin = rule_entry.get("rule", {}).get("origin")
    if exclude_user_agent_rules and origin == "user-agent":
        return False
    return True


def _summarize_inherited_styles(
    entries: List[Dict[str, Any]],
    *,
    exclude_user_agent_rules: bool,
) -> List[Dict[str, Any]]:
    inherited: List[Dict[str, Any]] = []
    for entry in entries:
        inline_style = entry.get("inlineStyle") or {}
        inherited_rules = [
            _summarize_rule_match(rule_entry)
            for rule_entry in entry.get("matchedCSSRules", [])
            if _rule_entry_allowed(rule_entry, exclude_user_agent_rules=exclude_user_agent_rules)
        ]
        inline_summary = {
            "styleSheetId": inline_style.get("styleSheetId"),
            "cssText": inline_style.get("cssText"),
        }
        payload: Dict[str, Any] = {"matchedCSSRules": inherited_rules}
        if inline_summary["cssText"]:
            payload["inlineStyle"] = inline_summary
        if inherited_rules or payload.get("inlineStyle"):
            inherited.append(payload)
    return inherited


def _summarize_matched_styles(
    matched: Dict[str, Any],
    *,
    exclude_user_agent_rules: bool,
) -> Dict[str, Any]:
    filtered_rule_entries = [
        rule_entry
        for rule_entry in matched.get("matchedCSSRules", [])
        if _rule_entry_allowed(rule_entry, exclude_user_agent_rules=exclude_user_agent_rules)
    ]
    matched_rules = [_summarize_rule_match(rule_entry) for rule_entry in filtered_rule_entries]

    inline_style = matched.get("inlineStyle") or {}
    attributes_style = matched.get("attributesStyle") or {}

    payload: Dict[str, Any] = {
        "ruleCount": len(matched_rules),
        "ruleMatches": matched_rules or None,
        "inheritedStyleEntries": _summarize_inherited_styles(
            matched.get("inherited", []),
            exclude_user_agent_rules=exclude_user_agent_rules,
        )
        or None,
    }

    if inline_style.get("cssText"):
        payload["inlineStyle"] = {
            "styleSheetId": inline_style.get("styleSheetId"),
            "cssText": inline_style.get("cssText"),
        }

    if attributes_style.get("cssText"):
        payload["attributesStyle"] = {
            "styleSheetId": attributes_style.get("styleSheetId"),
            "cssText": attributes_style.get("cssText"),
        }

    return payload


def _collect_declared_color_props(
    matched: Dict[str, Any],
    *,
    exclude_user_agent_rules: bool,
) -> Set[str]:
    names: Set[str] = set()

    inline_style = matched.get("inlineStyle") or {}
    attributes_style = matched.get("attributesStyle") or {}
    names.update(_extract_declared_property_names(inline_style))
    names.update(_extract_declared_property_names(attributes_style))

    for rule_entry in matched.get("matchedCSSRules", []) or []:
        if not _rule_entry_allowed(rule_entry, exclude_user_agent_rules=exclude_user_agent_rules):
            continue
        rule_style = rule_entry.get("rule", {}).get("style", {})
        names.update(_extract_declared_property_names(rule_style))

    for inherited in matched.get("inherited", []) or []:
        inline_style = inherited.get("inlineStyle") or {}
        names.update(_extract_declared_property_names(inline_style))
        for rule_entry in inherited.get("matchedCSSRules", []) or []:
            if not _rule_entry_allowed(rule_entry, exclude_user_agent_rules=exclude_user_agent_rules):
                continue
            rule_style = rule_entry.get("rule", {}).get("style", {})
            names.update(_extract_declared_property_names(rule_style))

    return names


def _filter_computed_colors(computed_colors: Dict[str, Any], declared_prop_names: Set[str]) -> Dict[str, Any]:
    filtered: Dict[str, Any] = {}
    for key, value in computed_colors.items():
        css_name = COLOR_PROP_TO_CSS_NAME.get(key)
        if css_name and css_name in declared_prop_names:
            filtered[key] = value

    # Keep at least color/currentColor for text contrast flow when nothing author-declared.
    if not filtered and "color" in computed_colors:
        filtered["color"] = computed_colors["color"]
        filtered["currentColor"] = computed_colors.get("currentColor", computed_colors["color"])

    return filtered


def _normalize_rule_usage(usage_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    usage = []
    for item in usage_payload.get("ruleUsage", []):
        usage.append(
            {
                "styleSheetId": item.get("styleSheetId"),
                "startOffset": item.get("startOffset"),
                "endOffset": item.get("endOffset"),
                "used": item.get("used"),
            }
        )
    return usage


def _collect_stylesheet_headers(cdp: Any) -> Dict[str, Dict[str, Any]]:
    headers: Dict[str, Dict[str, Any]] = {}

    def _on_style_added(params: Dict[str, Any]) -> None:
        header = (params or {}).get("header", {})
        style_sheet_id = header.get("styleSheetId")
        if not style_sheet_id:
            return
        headers[style_sheet_id] = {
            "styleSheetId": style_sheet_id,
            "sourceURL": header.get("sourceURL") or None,
            "title": header.get("title") or None,
            "isInline": header.get("isInline"),
            "origin": header.get("origin"),
        }

    cdp.on("CSS.styleSheetAdded", _on_style_added)
    return headers


def _inject_stylesheet_info(rule_matches: List[Dict[str, Any]], sheet_headers: Dict[str, Dict[str, Any]]) -> None:
    for match in rule_matches:
        style_sheet_id = match.get("styleSheetId")
        match["styleSheet"] = sheet_headers.get(style_sheet_id)


def _enrich_with_cdp(
    page: Page,
    snapshot: Dict[str, Any],
    include_invisible: bool,
    *,
    exclude_user_agent_rules: bool,
) -> Dict[str, Any]:
    cdp = page.context.new_cdp_session(page)
    stylesheet_headers = _collect_stylesheet_headers(cdp)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    cdp.send("CSS.startRuleUsageTracking")

    root = cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
    root_node_id = root["root"]["nodeId"]

    enriched_nodes = []

    for node in snapshot.get("nodes", []):
        if not include_invisible and not node.get("visible"):
            continue

        declared_sources: Dict[str, Any] = {}
        effective_background = None

        try:
            found = cdp.send("DOM.querySelector", {"nodeId": root_node_id, "selector": node.get("domPath")})
            cdp_node_id = found.get("nodeId")

            if cdp_node_id:
                matched = cdp.send("CSS.getMatchedStylesForNode", {"nodeId": cdp_node_id})
                declared_sources["cdpMatchedStyles"] = _summarize_matched_styles(
                    matched,
                    exclude_user_agent_rules=exclude_user_agent_rules,
                )
                _inject_stylesheet_info(
                    declared_sources["cdpMatchedStyles"].get("ruleMatches", []),
                    stylesheet_headers,
                )
                for inherited in declared_sources["cdpMatchedStyles"].get("inheritedStyleEntries", []):
                    _inject_stylesheet_info(inherited.get("matchedCSSRules", []), stylesheet_headers)

                declared_color_props = _collect_declared_color_props(
                    matched,
                    exclude_user_agent_rules=exclude_user_agent_rules,
                )
                node["computedColors"] = _filter_computed_colors(node.get("computedColors", {}), declared_color_props)

                try:
                    bg = cdp.send("CSS.getBackgroundColors", {"nodeId": cdp_node_id})
                    declared_sources["backgroundColors"] = bg.get("backgroundColors") or None
                    declared_sources["computedFontSize"] = bg.get("computedFontSize") or None
                    declared_sources["computedFontWeight"] = bg.get("computedFontWeight") or None
                    backgrounds = bg.get("backgroundColors", [])
                    effective_background = backgrounds[0] if backgrounds else None
                except Exception as bg_error:
                    declared_sources["backgroundSamplingError"] = str(bg_error)
            else:
                declared_sources["cdpMatchedStyles"] = {"error": "Node not found by selector"}

        except Exception as cdp_error:
            declared_sources["cdpMatchedStyles"] = {"error": str(cdp_error)}

        enriched_nodes.append(
            {
                **node,
                "effectiveBackground": effective_background,
                "declaredSources": declared_sources,
            }
        )

    rule_usage_payload = cdp.send("CSS.stopRuleUsageTracking")
    snapshot["ruleUsage"] = _normalize_rule_usage(rule_usage_payload)
    snapshot["nodes"] = enriched_nodes
    snapshot["domPathsInOrder"] = [node.get("domPath") for node in enriched_nodes]
    return snapshot


def extract_render_snapshot(
    html_content: str,
    base_path: str,
    output_json_path: Optional[str] = None,
    options: Optional[SnapshotOptions] = None,
) -> Dict[str, Any]:
    options = options or SnapshotOptions()
    temp_html_path = write_temp_html(html_content, base_path)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"file://{temp_html_path}", wait_until="load")
            page.wait_for_load_state("networkidle")
            page.evaluate("() => document.fonts && document.fonts.ready")
            page.wait_for_timeout(options.wait_after_load_ms)

            snapshot = page.evaluate(_build_dom_probe_js())
            snapshot = _enrich_with_cdp(
                page=page,
                snapshot=snapshot,
                include_invisible=options.include_invisible,
                exclude_user_agent_rules=options.exclude_user_agent_rules,
            )

            browser.close()
    finally:
        remove_temp_html(temp_html_path)

    snapshot["metadata"] = {
        "module": "module-1-snapshot-extraction",
        "basePath": os.path.abspath(base_path),
        "nodeCount": len(snapshot.get("nodes", [])),
        "capturedAt": datetime.now(timezone.utc).isoformat(),
        "cdp": {
            "includes": [
                "CSS.getBackgroundColors",
                "CSS.getMatchedStylesForNode",
                "CSS.startRuleUsageTracking",
                "CSS.stopRuleUsageTracking",
            ]
        },
    }

    if output_json_path:
        output_dir = os.path.dirname(output_json_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)

    return snapshot


def snapshot_options_to_dict(options: SnapshotOptions) -> Dict[str, Any]:
    return asdict(options)
