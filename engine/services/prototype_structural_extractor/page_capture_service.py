from __future__ import annotations

import os
from typing import Any

from playwright.sync_api import Browser, Page, sync_playwright

from app.config import get_artifacts_dir
from engine.models.prototype_structural_extractor.snapshot_models import SnapshotOptions
from engine.services.prototype_structural_extractor.page_stabilization_service import (
    wait_for_render_stability,
)
from engine.services.prototype_structural_extractor.render_io_service import (
    remove_temp_render_html,
    write_temp_render_html,
)
from engine.utils.file_utils import ensure_parent_dir


def create_render_page(
    html_content: str,
    base_path: str,
    *,
    options: SnapshotOptions,
) -> tuple[Any, Browser, Page, str, dict]:
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
    return playwright, browser, page, temp_html_path, stability


def close_render_page(playwright: Any, browser: Browser, temp_html_path: str) -> None:
    try:
        browser.close()
    finally:
        try:
            playwright.stop()
        finally:
            remove_temp_render_html(temp_html_path)


def capture_full_page_screenshot(page: Page, output_image: str) -> str:
    ensure_parent_dir(output_image)
    page.screenshot(path=output_image, full_page=True)
    return output_image


def render_prototype(
    html_content: str,
    base_path: str,
    output_image: str | None = None,
    session_id: str | None = None,
    initial_viewport_width: int = 1440,
    initial_viewport_height: int = 900,
    wait_ms: int = 700,
):
    if output_image is None:
        session_key = session_id or "default"
        output_image = os.path.join(get_artifacts_dir(session_key), "prototype_screenshot.png")

    options = SnapshotOptions(
        wait_after_load_ms=wait_ms,
        initial_viewport_width=initial_viewport_width,
        initial_viewport_height=initial_viewport_height,
    )
    playwright, browser, page, temp_html_path, _ = create_render_page(
        html_content,
        base_path,
        options=options,
    )
    try:
        return capture_full_page_screenshot(page, output_image)
    finally:
        close_render_page(playwright, browser, temp_html_path)
