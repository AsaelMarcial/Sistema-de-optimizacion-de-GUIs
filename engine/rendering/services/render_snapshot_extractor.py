import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page, sync_playwright

from engine.rendering.utils.screenshot_utils import remove_temp_html, write_temp_html


@dataclass
class SnapshotOptions:
    wait_after_load_ms: int = 500
    include_invisible: bool = True


def _build_dom_probe_js() -> str:
    return """
    () => {
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

      const styleOf = (el) => window.getComputedStyle(el);
      const nodes = [];
      const all = Array.from(document.querySelectorAll('*'));

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
    """


def _summarize_selector_list(rule: Dict[str, Any]) -> Dict[str, Any]:
    selector_list = rule.get("selectorList", {})
    selectors = selector_list.get("selectors", [])
    return {
        "text": selector_list.get("text"),
        "selectors": selectors,
    }


def _summarize_rule_match(rule_entry: Dict[str, Any]) -> Dict[str, Any]:
    rule = rule_entry.get("rule", {})
    style = rule.get("style", {})
    return {
        "matchingSelectors": rule_entry.get("matchingSelectors", []),
        "origin": rule.get("origin"),
        "styleSheetId": style.get("styleSheetId"),
        "range": style.get("range"),
        "selectorList": _summarize_selector_list(rule),
    }


def _summarize_inherited_styles(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    inherited: List[Dict[str, Any]] = []
    for entry in entries:
        inline_style = entry.get("inlineStyle", {}) or {}
        inherited.append(
            {
                "inlineStyle": {
                    "styleSheetId": inline_style.get("styleSheetId"),
                    "cssText": inline_style.get("cssText"),
                },
                "matchedCSSRules": [
                    _summarize_rule_match(rule_entry)
                    for rule_entry in entry.get("matchedCSSRules", [])
                ],
            }
        )
    return inherited


def _summarize_matched_styles(matched: Dict[str, Any]) -> Dict[str, Any]:
    matched_rules = [_summarize_rule_match(rule_entry) for rule_entry in matched.get("matchedCSSRules", [])]
    inline_style = matched.get("inlineStyle")
    inherited_entries = matched.get("inherited", [])

    return {
        "ruleCount": len(matched_rules),
        "ruleMatches": matched_rules,
        "hasInlineStyle": inline_style is not None,
        "inlineStyle": {
            "styleSheetId": (inline_style or {}).get("styleSheetId"),
            "cssText": (inline_style or {}).get("cssText"),
        },
        "inheritedStyleEntries": _summarize_inherited_styles(inherited_entries),
    }


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


def _enrich_with_cdp(page: Page, snapshot: Dict[str, Any], include_invisible: bool) -> Dict[str, Any]:
    cdp = page.context.new_cdp_session(page)
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
                declared_sources["cdpMatchedStyles"] = _summarize_matched_styles(matched)

                try:
                    declared_sources["boxModel"] = cdp.send("DOM.getBoxModel", {"nodeId": cdp_node_id})
                except Exception as box_error:
                    declared_sources["boxModelError"] = str(box_error)

                try:
                    bg = cdp.send("CSS.getBackgroundColors", {"nodeId": cdp_node_id})
                    declared_sources["backgroundColors"] = bg.get("backgroundColors", [])
                    declared_sources["computedFontSize"] = bg.get("computedFontSize")
                    declared_sources["computedFontWeight"] = bg.get("computedFontWeight")
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
                "DOM.getBoxModel",
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
