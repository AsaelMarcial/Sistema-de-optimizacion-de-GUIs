import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

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
          computedColors: {
            color: style.color,
            backgroundColor: style.backgroundColor,
            borderColor: style.borderColor,
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


def _summarize_matched_styles(matched: Dict[str, Any]) -> Dict[str, Any]:
    rules = []
    for rule_entry in matched.get("matchedCSSRules", []):
        rule = rule_entry.get("rule", {})
        selector_text = ""
        selector_list = rule.get("selectorList", {})
        selectors = selector_list.get("selectors", [])
        if selectors:
            selector_text = ", ".join(sel.get("text", "") for sel in selectors if sel.get("text"))

        style = rule.get("style", {})
        rules.append(
            {
                "selector": selector_text,
                "origin": rule.get("origin"),
                "styleSheetId": style.get("styleSheetId"),
                "range": style.get("range"),
            }
        )

    inline_style = matched.get("inlineStyle")

    return {
        "ruleCount": len(rules),
        "rules": rules,
        "hasInlineStyle": inline_style is not None,
    }


def _enrich_with_cdp(page: Page, snapshot: Dict[str, Any], include_invisible: bool) -> Dict[str, Any]:
    cdp = page.context.new_cdp_session(page)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")

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
                    bg = cdp.send("CSS.getBackgroundColors", {"nodeId": cdp_node_id})
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
