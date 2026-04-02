from __future__ import annotations

import os

from app.config import get_artifacts_dir
from engine.adapters.browser.page_builder import CAPTURE_NODE_ID_ATTRIBUTE, PageBuilder
from engine.adapters.browser.render_models import SnapshotOptions


def render_prototype(
    html_content: str,
    base_path: str,
    output_image: str | None = None,
    session_id: str | None = None,
    initial_viewport_width: int = 1440,
    initial_viewport_height: int = 900,
    wait_ms: int = 700,
) -> str:
    if output_image is None:
        session_key = session_id or "default"
        output_image = os.path.join(get_artifacts_dir(session_key), "prototype_screenshot.png")

    builder = PageBuilder.start(
        html_content,
        base_path,
        options=SnapshotOptions(
            wait_after_load_ms=wait_ms,
            initial_viewport_width=initial_viewport_width,
            initial_viewport_height=initial_viewport_height,
        ),
    )
    try:
        screenshot_path, _ = builder.capture_screenshot_and_color_frequencies(
            output_image_path=output_image,
            session_id=session_id,
        )
        return screenshot_path or output_image
    finally:
        builder.close()
