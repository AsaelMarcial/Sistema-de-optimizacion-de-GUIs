from __future__ import annotations

import os
from typing import Any

from app.config import get_artifacts_dir
from engine.enums.scope import get_in_scope_css_properties
from engine.file_handling.services.artifact_storage_service import save_json
from engine.rendering.models.snapshot_models import RenderArtifacts, SnapshotOptions
from engine.rendering.services.layout_snapshot_service import build_layout_nodes, capture_layout_snapshot
from engine.rendering.services.page_capture_service import (
    capture_full_page_screenshot,
    close_render_page,
    create_render_page,
)
from engine.rendering.services.snapshot_normalization_service import normalize_snapshot_nodes
from engine.rendering.services.style_trace_service import (
    collect_style_information,
    register_stylesheet_headers,
)
from engine.rendering.utils.image_color_utils import pixels_to_color_frequency


def capture_page_artifacts(
    html_content: str,
    base_path: str,
    *,
    options: SnapshotOptions | None = None,
    session_id: str | None = None,
    output_json_path: str | None = None,
    output_image_path: str | None = None,
) -> RenderArtifacts:
    options = options or SnapshotOptions()
    if output_image_path is None and options.capture_screenshot:
        session_key = session_id or "default"
        output_image_path = os.path.join(get_artifacts_dir(session_key), "gui_screenshot.png")

    playwright, browser, page, temp_html_path, _ = create_render_page(
        html_content,
        base_path,
        options=options,
    )
    try:
        cdp = page.context.new_cdp_session(page)
        stylesheet_headers = register_stylesheet_headers(cdp)
        computed_style_whitelist = [spec.property_id.value for spec in get_in_scope_css_properties()]
        layout_snapshot_payload = capture_layout_snapshot(cdp, page, computed_style_whitelist)
        raw_nodes, document_metrics = build_layout_nodes(layout_snapshot_payload)
        for raw_node in raw_nodes:
            raw_node["node_id"] = f"node-{raw_node['document_order']}"

        style_traces, rules_used, palette = collect_style_information(
            cdp,
            raw_nodes,
            stylesheet_headers,
            include_user_agent_rules=options.include_user_agent_rules,
        )
        snapshot = normalize_snapshot_nodes(
            raw_nodes,
            style_traces,
            rules_used,
            palette,
            options=options,
            base_path=os.path.abspath(base_path),
            document_metrics=document_metrics,
        )

        screenshot_path = None
        if options.capture_screenshot and output_image_path:
            screenshot_path = capture_full_page_screenshot(page, output_image_path)

        if output_json_path:
            save_json(output_json_path, snapshot.to_dict())

        color_frequencies = None
        if options.include_color_frequencies and screenshot_path:
            color_frequencies = pixels_to_color_frequency(screenshot_path)

        return RenderArtifacts(
            screenshot_path=screenshot_path,
            snapshot=snapshot,
            snapshot_json_path=output_json_path,
            color_frequencies=color_frequencies,
        )
    finally:
        close_render_page(playwright, browser, temp_html_path)


def extract_render_snapshot(
    html_content: str,
    base_path: str,
    output_json_path: str | None = None,
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
    artifacts = capture_page_artifacts(
        html_content=html_content,
        base_path=base_path,
        output_json_path=output_json_path,
        options=options,
    )
    return artifacts.snapshot.to_dict()
