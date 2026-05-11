from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from playwright.sync_api import sync_playwright

from engine.adapters.browser.layout_snapshot import build_layout_nodes, capture_layout_snapshot
from engine.adapters.browser.render_io import remove_temp_render_html, write_temp_render_html
from engine.adapters.browser.render_models import RenderSnapshot, SnapshotOptions
from engine.adapters.browser.style_trace import collect_style_information, register_stylesheet_headers
from engine.adapters.file_system.file_manager import ensure_parent_dir
from engine.domain.enums.scope.css_properties import get_in_scope_css_properties
from engine.domain.models.color import ColorCatalog
from engine.domain.models.style import StyleCatalog
from engine.domain.utils.parsers import normalize_snapshot_nodes


@dataclass(slots=True)
class PageBuilder:
    html_content: str
    base_path: str
    options: SnapshotOptions = field(default_factory=SnapshotOptions)
    playwright: Any = field(init=False, repr=False)
    browser: Any = field(init=False, repr=False)
    page: Any = field(init=False, repr=False)
    cdp_session: Any = field(init=False, repr=False)
    temp_html_path: str = field(init=False)

    @classmethod
    def new(
        cls,
        html_content: str,
        base_path: str,
        *,
        options: SnapshotOptions | None = None,
        existing: "PageBuilder | None" = None,
    ) -> "PageBuilder":
        if existing is not None and existing.is_open:
            raise ValueError("Ya existe una instancia activa de PageBuilder.")
        return cls(
            html_content=html_content,
            base_path=base_path,
            options=options or SnapshotOptions(),
        )

    def __post_init__(self) -> None:
        self.temp_html_path = write_temp_render_html(self.html_content, self.base_path)
        playwright = None
        browser = None
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={
                    "width": int(self.options.initial_viewport_width),
                    "height": int(self.options.initial_viewport_height),
                }
            )
            page.set_default_timeout(30000)
            page.set_default_navigation_timeout(30000)
            page.goto(f"file://{self.temp_html_path}", wait_until="load")
            self.playwright = playwright
            self.browser = browser
            self.page = page
            self.cdp_session = page.context.new_cdp_session(page)
            self._register_close_handlers()
            self.wait_for_render_ready()
        except Exception:
            if browser is not None:
                try:
                    browser.close()
                except Exception:
                    pass
            if playwright is not None:
                try:
                    playwright.stop()
                except Exception:
                    pass
            remove_temp_render_html(self.temp_html_path)
            raise

    @property
    def is_open(self) -> bool:
        page_is_closed = getattr(self.page, "is_closed", None)
        browser_is_connected = getattr(self.browser, "is_connected", None)
        return not (
            callable(page_is_closed)
            and page_is_closed()
        ) and (
            not callable(browser_is_connected)
            or browser_is_connected()
        )

    def _ensure_open(self) -> None:
        if not self.is_open:
            raise RuntimeError("PageBuilder esta cerrado.")

    def _register_close_handlers(self) -> None:
        def _handle_close(*_args: Any) -> None:
            remove_temp_render_html(self.temp_html_path)

        for target in (self.cdp_session, self.page, self.browser):
            on = getattr(target, "on", None)
            if callable(on):
                try:
                    on("close", _handle_close)
                except Exception:
                    pass
        on = getattr(self.browser, "on", None)
        if callable(on):
            try:
                on("disconnected", _handle_close)
            except Exception:
                pass

    def close(self) -> None:
        if not self.is_open:
            remove_temp_render_html(self.temp_html_path)
            return
        try:
            detach = getattr(self.cdp_session, "detach", None)
            if callable(detach):
                try:
                    detach()
                except Exception:
                    pass
            self.browser.close()
        finally:
            try:
                self.playwright.stop()
            finally:
                remove_temp_render_html(self.temp_html_path)

    def load(self, html_content: str, base_path: str) -> None:
        self._ensure_open()
        remove_temp_render_html(self.temp_html_path)
        self.html_content = html_content
        self.temp_html_path = write_temp_render_html(html_content, base_path)
        self.base_path = base_path
        self.page.goto(f"file://{self.temp_html_path}", wait_until="load")
        self.wait_for_render_ready()

    def wait_for_render_ready(self) -> None:
        self._ensure_open()
        self.page.wait_for_load_state("domcontentloaded")
        self.page.wait_for_load_state("load")
        self.page.wait_for_function(
            """
            () => document.readyState === 'complete'
            """
        )
        self.page.wait_for_function(
            """
            () => {
              if (!document.fonts || !document.fonts.ready) {
                return true;
              }
              return document.fonts.ready.then(() => true).catch(() => true);
            }
            """
        )
        self.page.wait_for_function(
            """
            async () => {
              const images = Array.from(document.images || []);
              await Promise.all(images.map((image) => {
                if (image.complete && image.naturalWidth !== 0) {
                  return Promise.resolve();
                }
                return image.decode ? image.decode().catch(() => null) : Promise.resolve();
              }));
              return true;
            }
            """
        )
        if self.options.wait_after_load_ms > 0:
            self.page.wait_for_timeout(self.options.wait_after_load_ms)

        self.page.evaluate(
            """
            async (stepPx) => {
              const root = document.scrollingElement || document.documentElement;
              const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight);
              const step = Math.max(stepPx, 1);
              for (let offset = 0; offset <= maxScroll; offset += step) {
                window.scrollTo(0, offset);
                await new Promise((resolve) => window.requestAnimationFrame(() => resolve()));
              }
              window.scrollTo(0, 0);
              await new Promise((resolve) => window.requestAnimationFrame(() => {
                window.requestAnimationFrame(() => resolve());
              }));
            }
            """,
            self.options.scroll_step_px,
        )

        previous_metrics = None
        matching_samples = 0
        for _ in range(self.options.max_render_ready_checks):
            metrics = self.page.evaluate(
                """
                () => {
                  const root = document.scrollingElement || document.documentElement;
                  return {
                    width: Math.max(root.scrollWidth, document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0),
                    height: Math.max(root.scrollHeight, document.documentElement.scrollHeight, document.body ? document.body.scrollHeight : 0),
                    viewportWidth: window.innerWidth,
                    viewportHeight: window.innerHeight,
                  };
                }
                """
            )
            if metrics == previous_metrics:
                matching_samples += 1
                if matching_samples >= 1:
                    break
            else:
                matching_samples = 0
                previous_metrics = metrics
            self.page.wait_for_timeout(self.options.render_ready_interval_ms)

    def capture_full_page_screenshot(
        self,
        *,
        output_path: str,
    ) -> str | None:
        self._ensure_open()
        if not self.options.capture_screenshot:
            return None

        output_image_path = str(output_path or "").strip()
        if not output_image_path:
            raise ValueError("La ruta del screenshot no puede estar vacia.")

        ensure_parent_dir(output_image_path)
        self.page.screenshot(path=output_image_path, full_page=True, caret="initial")
        return output_image_path

    def capture_snapshot_models(self) -> tuple[RenderSnapshot, StyleCatalog, ColorCatalog]:
        self._ensure_open()
        cdp = self.cdp_session
        stylesheet_headers = register_stylesheet_headers(cdp)
        computed_style_whitelist = [spec.value for spec in get_in_scope_css_properties()]
        layout_snapshot_payload = capture_layout_snapshot(cdp, self.page, computed_style_whitelist)
        raw_nodes, document_metrics = build_layout_nodes(layout_snapshot_payload)
        for raw_node in raw_nodes:
            raw_node["node_id"] = str(raw_node["backend_node_id"])

        style_traces, style_catalog, colors_inventory = collect_style_information(
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
        return snapshot, style_catalog, colors_inventory
