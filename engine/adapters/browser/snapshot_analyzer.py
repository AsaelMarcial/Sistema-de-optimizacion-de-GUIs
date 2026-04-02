from typing import Any

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.browser.css_overview import capture_css_overview
from engine.adapters.browser.render_models import RenderArtifacts, SnapshotOptions


def capture_prototype_state_artifacts(
    html_content: str,
    base_path: str,
    *,
    options: SnapshotOptions | None = None,
    session_id: str | None = None,
    output_image_path: str | None = None,
    page_builder: PageBuilder | None = None,
) -> RenderArtifacts:
    options = options or SnapshotOptions()
    owns_page_builder = page_builder is None
    builder = page_builder or PageBuilder.start(
        html_content,
        base_path,
        options=options,
    )
    try:
        return builder.capture_state_artifacts(
            output_image_path=output_image_path,
            session_id=session_id,
        )
    finally:
        if owns_page_builder:
            builder.close()


def capture_render_screenshot_and_color_frequencies(
    html_content: str,
    base_path: str,
    *,
    options: SnapshotOptions | None = None,
    session_id: str | None = None,
    output_image_path: str | None = None,
    page_builder: PageBuilder | None = None,
) -> tuple[str | None, list[dict[str, Any]] | None]:
    options = options or SnapshotOptions(include_color_frequencies=True, capture_screenshot=True)
    owns_page_builder = page_builder is None
    builder = page_builder or PageBuilder.start(
        html_content,
        base_path,
        options=options,
    )
    try:
        return builder.capture_screenshot_and_color_frequencies(
            output_image_path=output_image_path,
            session_id=session_id,
        )
    finally:
        if owns_page_builder:
            builder.close()


def extract_prototype_state_snapshot(
    html_content: str,
    base_path: str,
    options: SnapshotOptions | None = None,
) -> dict[str, Any]:
    if options is None:
        options = SnapshotOptions(capture_screenshot=False)
    else:
        options = SnapshotOptions(
            wait_after_load_ms=options.wait_after_load_ms,
            include_invisible=options.include_invisible,
            include_user_agent_rules=options.include_user_agent_rules,
            include_color_frequencies=options.include_color_frequencies,
            capture_screenshot=False,
            initial_viewport_width=options.initial_viewport_width,
            initial_viewport_height=options.initial_viewport_height,
            scroll_step_px=options.scroll_step_px,
            max_stability_checks=options.max_stability_checks,
            stability_interval_ms=options.stability_interval_ms,
        )
    artifacts = capture_prototype_state_artifacts(
        html_content=html_content,
        base_path=base_path,
        options=options,
    )
    return artifacts.snapshot.to_dict()


def extract_prototype_css_overview(
    html_content: str,
    base_path: str,
    options: SnapshotOptions | None = None,
) -> dict[str, Any]:
    options = options or SnapshotOptions(capture_screenshot=False)
    builder = PageBuilder.start(
        html_content,
        base_path,
        options=options,
    )
    try:
        return capture_css_overview(builder.page)
    finally:
        builder.close()
