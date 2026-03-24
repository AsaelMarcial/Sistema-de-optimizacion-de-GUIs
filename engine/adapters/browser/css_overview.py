from __future__ import annotations

from collections import defaultdict
from typing import Any

from playwright.sync_api import Page

from engine.adapters.browser.prototype_renderer import CAPTURE_NODE_ID_ATTRIBUTE
from engine.domain.utils.coloraide import color_to_hex, color_to_rgba_tuple, composite_over, contrast_ratio

_CSS_OVERVIEW_CAPTURE_SCRIPT = """
() => {
  const captureNodeIdAttribute = '__CAPTURE_NODE_ID_ATTRIBUTE__';
  const normalizeText = (value) => String(value || '').replace(/\\s+/g, ' ').trim();

  const selectorToken = (element) => {
    let token = element.tagName.toLowerCase();
    if (element.id) {
      token += `#${CSS.escape(element.id)}`;
    }

    const classes = Array.from(element.classList || []).slice(0, 2);
    if (classes.length) {
      token += classes.map((name) => `.${CSS.escape(name)}`).join('');
    }

    return token;
  };

  const selectorPath = (element) => {
    const parts = [];
    let current = element;

    while (current && current.nodeType === Node.ELEMENT_NODE && parts.length < 6) {
      let token = selectorToken(current);
      if (!current.id && current.parentElement) {
        const siblings = Array.from(current.parentElement.children).filter(
          (node) => node.tagName === current.tagName,
        );
        if (siblings.length > 1) {
          token += `:nth-of-type(${siblings.indexOf(current) + 1})`;
        }
      }

      parts.unshift(token);
      if (current.id) {
        break;
      }
      current = current.parentElement;
    }

    return parts.join(' > ');
  };

  const directText = (element) => {
    const parts = [];
    for (const node of Array.from(element.childNodes)) {
      if (node.nodeType !== Node.TEXT_NODE) {
        continue;
      }

      const value = normalizeText(node.textContent);
      if (value) {
        parts.push(value);
      }
    }

    if (parts.length) {
      return parts.join(' ').slice(0, 160);
    }

    const fallback = normalizeText(
      element.getAttribute('aria-label') ||
      element.getAttribute('placeholder') ||
      (typeof element.value === 'string' ? element.value : '')
    );
    return fallback.slice(0, 160);
  };

  const isVisible = (style, rect) => {
    if (!style) {
      return false;
    }

    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity || '1') === 0) {
      return false;
    }

    return rect.width > 0 && rect.height > 0;
  };

  const backgroundStack = (element) => {
    const colors = [];
    let current = element;
    while (current && current.nodeType === Node.ELEMENT_NODE) {
      const currentStyle = getComputedStyle(current);
      if (currentStyle.backgroundColor) {
        colors.push(currentStyle.backgroundColor);
      }
      current = current.parentElement;
    }

    if (!colors.length) {
      colors.push('rgb(255, 255, 255)');
    }

    return colors;
  };

  const replacedTags = new Set([
    'audio',
    'canvas',
    'embed',
    'iframe',
    'img',
    'input',
    'meter',
    'object',
    'progress',
    'select',
    'svg',
    'textarea',
    'video',
  ]);

  const unusedReason = (element, propertyName) => {
    const style = getComputedStyle(element);
    const parentStyle = element.parentElement ? getComputedStyle(element.parentElement) : null;
    const display = style.display;
    const position = style.position;
    const parentDisplay = parentStyle ? parentStyle.display : '';
    const isInline = display === 'inline';
    const isReplacedElement = replacedTags.has(element.tagName.toLowerCase());
    const isFlexItem = parentDisplay === 'flex' || parentDisplay === 'inline-flex';
    const isGridItem = parentDisplay === 'grid' || parentDisplay === 'inline-grid';

    switch (propertyName) {
      case 'top':
      case 'right':
      case 'bottom':
      case 'left':
        return position === 'static'
          ? 'offset properties do not affect static-positioned elements'
          : null;
      case 'z-index':
        return position === 'static'
          ? 'z-index has no effect on non-positioned elements'
          : null;
      case 'width':
      case 'height':
        return isInline && !isReplacedElement
          ? 'width/height do not apply to inline non-replaced elements'
          : null;
      case 'vertical-align':
        return ['inline', 'inline-block', 'table-cell'].includes(display)
          ? null
          : 'vertical-align does not apply to this display type';
      case 'order':
      case 'flex-grow':
      case 'flex-shrink':
      case 'flex-basis':
        return isFlexItem ? null : 'flex item property used outside a flex container';
      case 'grid-column':
      case 'grid-row':
      case 'grid-area':
      case 'justify-self':
        return isGridItem ? null : 'grid item property used outside a grid container';
      case 'align-self':
      case 'place-self':
        return isFlexItem || isGridItem
          ? null
          : 'self-alignment property used outside flex/grid';
      default:
        return null;
    }
  };

  const unusedDeclarations = [];
  const unusedDeclarationKeys = new Set();

  const recordUnusedDeclaration = (element, sourceKind, source, ruleSelector, propertyName, value) => {
    const reason = unusedReason(element, propertyName);
    if (!reason) {
      return;
    }

    const selector = selectorPath(element);
    const key = JSON.stringify([selector, sourceKind, source || '', ruleSelector || '', propertyName, value, reason]);
    if (unusedDeclarationKeys.has(key)) {
      return;
    }
    unusedDeclarationKeys.add(key);

    unusedDeclarations.push({
      selector,
      tag_name: element.tagName.toLowerCase(),
      property: propertyName,
      value: normalizeText(value),
      reason,
      source_kind: sourceKind,
      source: source || null,
      rule_selector: ruleSelector || null,
    });
  };

  const collectUnusedDeclarations = (rules, source) => {
    for (const rule of Array.from(rules || [])) {
      if (rule.type === CSSRule.STYLE_RULE) {
        let matches = [];
        try {
          matches = Array.from(document.querySelectorAll(rule.selectorText));
        } catch (error) {}

        for (const element of matches) {
          for (const propertyName of Array.from(rule.style || [])) {
            recordUnusedDeclaration(
              element,
              'stylesheet',
              source,
              rule.selectorText || null,
              propertyName,
              rule.style.getPropertyValue(propertyName),
            );
          }
        }
        continue;
      }

      if ('cssRules' in rule && rule.cssRules) {
        try {
          collectUnusedDeclarations(rule.cssRules, source);
        } catch (error) {}
      }
    }
  };

  const mediaQueryCount = new Map();

  const collectMediaRules = (rules, source) => {
    for (const rule of Array.from(rules || [])) {
      if (rule.type === CSSRule.MEDIA_RULE) {
        const text = normalizeText(rule.conditionText || (rule.media ? rule.media.mediaText : ''));
        if (text) {
          const key = JSON.stringify([source, text]);
          mediaQueryCount.set(key, (mediaQueryCount.get(key) || 0) + 1);
        }
        try {
          collectMediaRules(rule.cssRules, source);
        } catch (error) {}
        continue;
      }

      if ('cssRules' in rule && rule.cssRules) {
        try {
          collectMediaRules(rule.cssRules, source);
        } catch (error) {}
      }
    }
  };

  const stylesheets = Array.from(document.styleSheets).map((sheet) => {
    const source = sheet.href || 'inline';
    let rulesCount = null;
    try {
      rulesCount = sheet.cssRules.length;
      collectMediaRules(sheet.cssRules, source);
      collectUnusedDeclarations(sheet.cssRules, source);
    } catch (error) {}

    return {
      href: sheet.href || null,
      is_inline: !sheet.href,
      rules_count: rulesCount,
    };
  });

  const mediaQueries = Array.from(mediaQueryCount.entries()).map(([key, occurrences]) => {
    const [source, text] = JSON.parse(key);
    return {
      source: source === 'inline' ? null : source,
      text,
      occurrences,
      matches: window.matchMedia(text).matches,
    };
  });

  const elements = Array.from(document.querySelectorAll('*')).map((element) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    return {
      node_id: element.getAttribute(captureNodeIdAttribute),
      tag_name: element.tagName.toLowerCase(),
      selector: selectorPath(element),
      id: element.id || null,
      class_list: Array.from(element.classList || []),
      text_sample: directText(element),
      is_visible: isVisible(style, rect),
      inline_style: element.getAttribute('style'),
      colors: {
        text: style.color,
        background: style.backgroundColor,
        border_top: style.borderTopColor,
        border_right: style.borderRightColor,
        border_bottom: style.borderBottomColor,
        border_left: style.borderLeftColor,
        fill: style.fill || null,
        stroke: style.stroke || null,
        effective_background_stack: backgroundStack(element),
      },
      typography: {
        font_family: style.fontFamily,
        font_size_px: Number.parseFloat(style.fontSize) || 0,
        font_weight: Number.parseInt(style.fontWeight, 10) || (style.fontWeight === 'bold' ? 700 : 400),
        line_height: style.lineHeight,
      },
      bounds: {
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      },
    };
  });

  for (const element of Array.from(document.querySelectorAll('[style]'))) {
    for (const propertyName of Array.from(element.style || [])) {
      recordUnusedDeclaration(
        element,
        'inline',
        null,
        null,
        propertyName,
        element.style.getPropertyValue(propertyName),
      );
    }
  }

  return {
    metadata: {
      url: window.location.href,
      title: document.title,
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
    },
    stylesheets,
    media_queries: mediaQueries,
    unused_declarations: unusedDeclarations,
    elements,
  };
}
""".replace("__CAPTURE_NODE_ID_ATTRIBUTE__", CAPTURE_NODE_ID_ATTRIBUTE)


def capture_css_overview(page: Page) -> dict[str, Any]:
    payload = page.evaluate(_CSS_OVERVIEW_CAPTURE_SCRIPT)
    return build_css_overview(payload)


def build_css_overview(payload: dict[str, Any]) -> dict[str, Any]:
    elements = tuple(payload.get("elements") or ())
    visible_elements = tuple(element for element in elements if element.get("is_visible"))
    contrast_issues = _build_contrast_issues(visible_elements)
    stylesheets = tuple(payload.get("stylesheets") or ())
    media_queries = _build_media_queries(payload.get("media_queries") or ())
    unused_declarations = _build_unused_declarations(payload.get("unused_declarations") or [])
    colors = {
        "text": _collect_color_entries(visible_elements, "text"),
        "background": _collect_color_entries(visible_elements, "background"),
        "border": _collect_border_color_entries(visible_elements),
        "fill": _collect_color_entries(visible_elements, "fill"),
        "stroke": _collect_color_entries(visible_elements, "stroke"),
    }
    typography = _build_typography(visible_elements)
    summary = {
        "element_count": len(elements),
        "visible_element_count": len(visible_elements),
        "text_element_count": sum(1 for element in visible_elements if str(element.get("text_sample") or "").strip()),
        "inline_style_count": sum(1 for element in elements if element.get("inline_style")),
        "stylesheet_count": len(stylesheets),
        "external_stylesheet_count": sum(1 for sheet in stylesheets if sheet.get("href")),
        "inline_stylesheet_count": sum(1 for sheet in stylesheets if not sheet.get("href")),
        "media_query_count": len(media_queries),
        "contrast_issue_count": len(contrast_issues),
        "unused_declaration_count": unused_declarations["count"],
    }

    return {
        "metadata": {
            **dict(payload.get("metadata") or {}),
            "generator": "css_overview_adapter",
        },
        "summary": summary,
        "stylesheets": {
            "entries": list(stylesheets),
        },
        "colors": colors,
        "typography": typography,
        "media_queries": media_queries,
        "contrast_issues": contrast_issues,
        "unused_declarations": unused_declarations,
        "unsupported_sections": [],
    }


def _build_media_queries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        text = str(entry.get("text") or "").strip()
        if not text:
            continue
        normalized.append(
            {
                "text": text,
                "matches": bool(entry.get("matches", False)),
                "occurrences": int(entry.get("occurrences") or 0),
                "source": entry.get("source") or None,
            }
        )

    normalized.sort(key=lambda item: (-item["occurrences"], item["text"]))
    return normalized


def _build_unused_declarations(entries: list[dict[str, Any]]) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    for entry in entries:
        property_name = str(entry.get("property") or "").strip()
        selector = str(entry.get("selector") or "").strip()
        if not property_name or not selector:
            continue

        normalized.append(
            {
                "selector": selector,
                "tag_name": str(entry.get("tag_name") or "").strip(),
                "property": property_name,
                "value": str(entry.get("value") or "").strip(),
                "reason": str(entry.get("reason") or "").strip(),
                "source_kind": str(entry.get("source_kind") or "").strip() or "stylesheet",
                "source": entry.get("source") or None,
                "rule_selector": entry.get("rule_selector") or None,
            }
        )

    normalized.sort(key=lambda item: (item["selector"], item["property"], item["source_kind"]))
    return {
        "count": len(normalized),
        "entries": normalized,
    }


def _collect_color_entries(elements: tuple[dict[str, Any], ...], color_key: str) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, float], dict[str, Any]] = {}
    for element in elements:
        colors = element.get("colors") or {}
        normalized = _normalize_color(colors.get(color_key))
        if normalized is None:
            continue

        bucket = buckets.setdefault(
            (normalized["hex"], normalized["alpha"]),
            {
                **normalized,
                "count": 0,
                "node_ids": [],
                "sample_selectors": [],
            },
        )
        bucket["count"] += 1
        _append_unique_value(bucket["node_ids"], element.get("node_id"))
        _append_sample_selector(bucket["sample_selectors"], element.get("selector"))

    return _sorted_entries(buckets.values())


def _collect_border_color_entries(elements: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, float], dict[str, Any]] = {}
    for element in elements:
        colors = element.get("colors") or {}
        for border_key in ("border_top", "border_right", "border_bottom", "border_left"):
            normalized = _normalize_color(colors.get(border_key))
            if normalized is None:
                continue

            bucket = buckets.setdefault(
                (normalized["hex"], normalized["alpha"]),
                {
                    **normalized,
                    "count": 0,
                    "node_ids": [],
                    "sample_selectors": [],
                },
            )
            bucket["count"] += 1
            _append_unique_value(bucket["node_ids"], element.get("node_id"))
            _append_sample_selector(bucket["sample_selectors"], element.get("selector"))

    return _sorted_entries(buckets.values())


def _build_typography(elements: tuple[dict[str, Any], ...]) -> dict[str, list[dict[str, Any]]]:
    families: dict[str, dict[str, Any]] = {}
    styles: dict[tuple[str, float, int, str], dict[str, Any]] = {}

    for element in elements:
        typography = element.get("typography") or {}
        font_family = str(typography.get("font_family") or "").strip()
        if not font_family:
            continue

        family_bucket = families.setdefault(
            font_family,
            {
                "font_family": font_family,
                "count": 0,
                "sample_selectors": [],
            },
        )
        family_bucket["count"] += 1
        _append_sample_selector(family_bucket["sample_selectors"], element.get("selector"))

        font_size_px = round(float(typography.get("font_size_px") or 0.0), 4)
        font_weight = int(typography.get("font_weight") or 400)
        line_height = str(typography.get("line_height") or "").strip() or "normal"
        style_bucket = styles.setdefault(
            (font_family, font_size_px, font_weight, line_height),
            {
                "font_family": font_family,
                "font_size_px": font_size_px,
                "font_weight": font_weight,
                "line_height": line_height,
                "count": 0,
                "sample_selectors": [],
            },
        )
        style_bucket["count"] += 1
        _append_sample_selector(style_bucket["sample_selectors"], element.get("selector"))

    return {
        "font_families": _sorted_entries(families.values(), *("font_family",)),
        "text_styles": _sorted_entries(styles.values(), *("font_family", "font_size_px", "font_weight", "line_height")),
    }


def _build_contrast_issues(elements: tuple[dict[str, Any], ...]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for element in elements:
        text_sample = str(element.get("text_sample") or "").strip()
        if not text_sample:
            continue

        colors = element.get("colors") or {}
        foreground = _normalize_color(colors.get("text"))
        background = _resolve_background_color(colors.get("effective_background_stack") or [])
        if foreground is None or background is None:
            continue

        try:
            effective_foreground: Any = foreground["color"]
            if foreground["alpha"] < 1.0:
                effective_foreground = composite_over(effective_foreground, background["color"])
            ratio = round(float(contrast_ratio(effective_foreground, background["color"])), 4)
        except Exception:
            continue

        typography = element.get("typography") or {}
        font_size_px = round(float(typography.get("font_size_px") or 0.0), 4)
        font_weight = int(typography.get("font_weight") or 400)
        large_text = font_size_px >= 24.0 or (font_size_px >= 18.667 and font_weight >= 700)
        required_ratio = 3.0 if large_text else 4.5
        if ratio >= required_ratio:
            continue

        issues.append(
            {
                "node_id": element.get("node_id") or None,
                "selector": element.get("selector") or "",
                "tag_name": element.get("tag_name") or "",
                "text_sample": text_sample,
                "contrast_ratio": ratio,
                "required_ratio": required_ratio,
                "is_large_text": large_text,
                "font_size_px": font_size_px,
                "font_weight": font_weight,
                "foreground": {
                    "css": foreground["css"],
                    "hex": foreground["hex"],
                    "alpha": foreground["alpha"],
                },
                "background": {
                    "css": background["css"],
                    "hex": background["hex"],
                    "alpha": background["alpha"],
                },
                "bounds": dict(element.get("bounds") or {}),
            }
        )

    issues.sort(key=lambda item: (item["contrast_ratio"], item["selector"]))
    return issues


def _resolve_background_color(stack: list[Any]) -> dict[str, Any] | None:
    composite: Any = "#ffffff"
    found_visible_layer = False
    for layer in reversed(stack):
        normalized = _normalize_color(layer)
        if normalized is None:
            continue
        found_visible_layer = True
        composite = composite_over(normalized["color"], composite)

    if not found_visible_layer:
        composite = "#ffffff"

    return _normalize_color(composite)


def _normalize_color(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None

    if isinstance(value, str):
        raw_value = value.strip()
        if not raw_value or raw_value.lower() in {"transparent", "none", "currentcolor", "inherit", "initial"}:
            return None
        color_value: Any = raw_value
    else:
        raw_value = ""
        color_value = value

    try:
        red, green, blue, alpha = color_to_rgba_tuple(color_value)
        if alpha <= 0:
            return None
        css_value = (
            f"rgba({red}, {green}, {blue}, {round(alpha, 4)})"
            if alpha < 1.0
            else f"rgb({red}, {green}, {blue})"
        )
        return {
            "css": css_value,
            "hex": color_to_hex(color_value),
            "alpha": round(alpha, 4),
            "rgba": [red, green, blue, round(alpha, 4)],
            "color": color_value,
        }
    except Exception:
        return None


def _append_sample_selector(target: list[str], selector: Any) -> None:
    normalized = str(selector or "").strip()
    if not normalized or normalized in target or len(target) >= 5:
        return
    target.append(normalized)


def _append_unique_value(target: list[str], value: Any) -> None:
    normalized = str(value or "").strip()
    if not normalized or normalized in target:
        return
    target.append(normalized)


def _sorted_entries(entries: Any, *extra_sort_keys: str) -> list[dict[str, Any]]:
    sort_keys = extra_sort_keys or ("hex",)
    return sorted(
        (dict(entry) for entry in entries),
        key=lambda item: tuple([-int(item.get("count") or 0), *[item.get(key) for key in sort_keys]]),
    )
