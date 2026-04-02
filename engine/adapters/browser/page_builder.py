from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

from app.config import get_artifacts_dir
from engine.adapters.browser.css_overview import capture_css_overview
from engine.adapters.browser.layout_snapshot import build_layout_nodes, capture_layout_snapshot
from engine.adapters.browser.page_stability import wait_for_render_stability
from engine.adapters.browser.render_io import remove_temp_render_html, write_temp_render_html
from engine.adapters.browser.render_models import RenderArtifacts, SnapshotOptions
from engine.adapters.browser.style_trace import collect_style_information, register_stylesheet_headers
from engine.adapters.utils.io import ensure_parent_dir
from engine.adapters.utils.screenshot import pixels_to_color_frequency
from engine.domain.data.css_properties import get_in_scope_css_properties
from engine.domain.utils.parsers import normalize_snapshot_nodes

CAPTURE_NODE_ID_ATTRIBUTE = "data-glow-capture-node-id"

_STAMP_CAPTURE_NODE_IDS_SCRIPT = f"""
() => {{
  let index = 0;
  for (const element of Array.from(document.querySelectorAll('*'))) {{
    index += 1;
    element.setAttribute('{CAPTURE_NODE_ID_ATTRIBUTE}', `node-${{index}}`);
  }}
  return index;
}}
"""


def _stamp_render_node_ids(page: Page) -> int:
    return int(page.evaluate(_STAMP_CAPTURE_NODE_IDS_SCRIPT) or 0)


def _create_page_runtime(
    html_content: str,
    base_path: str,
    *,
    options: SnapshotOptions,
) -> tuple[Any, Browser, Page, str, dict[str, Any]]:
    temp_html_path = write_temp_render_html(html_content, base_path)
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page(
        viewport={
            "width": int(options.initial_viewport_width),
            "height": int(options.initial_viewport_height),
        }
    )
    page.goto(f"file://{temp_html_path}", wait_until="load")
    stability = wait_for_render_stability(
        page,
        wait_after_load_ms=options.wait_after_load_ms,
        stability_interval_ms=options.stability_interval_ms,
        max_checks=options.max_stability_checks,
        scroll_step_px=options.scroll_step_px,
    )
    _stamp_render_node_ids(page)
    return playwright, browser, page, temp_html_path, stability


def _close_page_runtime(playwright: Any, browser: Browser, temp_html_path: str) -> None:
    try:
        browser.close()
    finally:
        try:
            playwright.stop()
        finally:
            remove_temp_render_html(temp_html_path)


def _capture_full_page_screenshot(page: Page, output_image: str) -> str:
    ensure_parent_dir(output_image)
    page.screenshot(path=output_image, full_page=True)
    return output_image


@dataclass(slots=True)
class PageBuilder:
    playwright: Any
    browser: Any
    page: Any
    temp_html_path: str
    stability: dict[str, Any]
    html_content: str
    base_path: str
    options: SnapshotOptions
    _closed: bool = field(default=False, init=False, repr=False)

    @classmethod
    def start(
        cls,
        html_content: str,
        base_path: str,
        *,
        options: SnapshotOptions | None = None,
    ) -> "PageBuilder":
        resolved_options = options or SnapshotOptions()
        playwright, browser, page, temp_html_path, stability = _create_page_runtime(
            html_content,
            base_path,
            options=resolved_options,
        )
        return cls(
            playwright=playwright,
            browser=browser,
            page=page,
            temp_html_path=temp_html_path,
            stability=stability,
            html_content=html_content,
            base_path=base_path,
            options=resolved_options,
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        _close_page_runtime(self.playwright, self.browser, self.temp_html_path)

    def capture_state_artifacts(
        self,
        *,
        output_image_path: str | None = None,
        session_id: str | None = None,
    ) -> RenderArtifacts:
        resolved_output_image = output_image_path
        if resolved_output_image is None and self.options.capture_screenshot:
            session_key = session_id or "default"
            resolved_output_image = os.path.join(
                get_artifacts_dir(session_key),
                "prototype_screenshot.png",
            )

        cdp = self.page.context.new_cdp_session(self.page)
        stylesheet_headers = register_stylesheet_headers(cdp)
        computed_style_whitelist = [spec.value for spec in get_in_scope_css_properties()]
        layout_snapshot_payload = capture_layout_snapshot(cdp, self.page, computed_style_whitelist)
        raw_nodes, document_metrics = build_layout_nodes(layout_snapshot_payload)
        for raw_node in raw_nodes:
            identity = raw_node.get("identity") or {}
            data_attributes = identity.get("data_attributes") or {}
            raw_node["node_id"] = (
                data_attributes.get(CAPTURE_NODE_ID_ATTRIBUTE)
                or f"node-doc-{raw_node['document_order']}"
            )

        style_traces, styles_inventory, colors_inventory = collect_style_information(
            cdp,
            raw_nodes,
            stylesheet_headers,
            include_user_agent_rules=self.options.include_user_agent_rules,
        )
        snapshot = normalize_snapshot_nodes(
            raw_nodes,
            style_traces,
            colors_inventory=colors_inventory,
            options=self.options,
            base_path=os.path.abspath(self.base_path),
            document_metrics=document_metrics,
        )
        css_overview = capture_css_overview(self.page)

        screenshot_path = None
        if self.options.capture_screenshot and resolved_output_image:
            screenshot_path = _capture_full_page_screenshot(self.page, resolved_output_image)

        color_frequencies = None
        if self.options.include_color_frequencies and screenshot_path:
            color_frequencies = pixels_to_color_frequency(screenshot_path)

        return RenderArtifacts(
            screenshot_path=screenshot_path,
            snapshot=snapshot,
            color_frequencies=color_frequencies,
            styles_inventory_seed=styles_inventory,
            colors_inventory_seed=colors_inventory,
            css_overview=css_overview,
        )

    def capture_screenshot_and_color_frequencies(
        self,
        *,
        output_image_path: str | None = None,
        session_id: str | None = None,
    ) -> tuple[str | None, list[dict[str, Any]] | None]:
        resolved_output_image = output_image_path
        if resolved_output_image is None and self.options.capture_screenshot:
            session_key = session_id or "default"
            resolved_output_image = os.path.join(
                get_artifacts_dir(session_key),
                "prototype_screenshot.png",
            )

        screenshot_path = None
        if self.options.capture_screenshot and resolved_output_image:
            screenshot_path = _capture_full_page_screenshot(self.page, resolved_output_image)

        color_frequencies = None
        if self.options.include_color_frequencies and screenshot_path:
            color_frequencies = pixels_to_color_frequency(screenshot_path)
        return screenshot_path, color_frequencies
