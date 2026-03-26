import os
from typing import Any

from app.config import get_artifacts_dir
from engine.adapters.browser.css_overview import capture_css_overview
from engine.adapters.browser.layout_snapshot import build_layout_nodes, capture_layout_snapshot
from engine.adapters.browser.prototype_renderer import (
    CAPTURE_NODE_ID_ATTRIBUTE,
    capture_full_page_screenshot,
    close_render_page,
    create_render_page,
)
from engine.adapters.browser.style_trace import collect_style_information, register_stylesheet_headers
from engine.adapters.utils.screenshot import pixels_to_color_frequency
from engine.adapters.utils.io import save_json
from engine.domain.data.css_properties import get_in_scope_css_properties
from engine.domain.models.snapshot import RenderArtifacts, SnapshotOptions
from engine.domain.utils.parsers import normalize_snapshot_nodes


def capture_prototype_state_artifacts(
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
        output_image_path = os.path.join(get_artifacts_dir(session_key), "prototype_screenshot.png")

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
            include_user_agent_rules=options.include_user_agent_rules,
        )
        snapshot = normalize_snapshot_nodes(
            raw_nodes,
            style_traces,
            options=options,
            base_path=os.path.abspath(base_path),
            document_metrics=document_metrics,
        )
        elements_inventory = snapshot.build_elements_inventory()
        css_overview = capture_css_overview(page)

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
            elements_inventory=elements_inventory,
            styles_inventory_seed=styles_inventory,
            colors_inventory_seed=colors_inventory,
            css_overview=css_overview,
        )
    finally:
        close_render_page(playwright, browser, temp_html_path)


def capture_render_screenshot_and_color_frequencies(
    html_content: str,
    base_path: str,
    *,
    options: SnapshotOptions | None = None,
    session_id: str | None = None,
    output_image_path: str | None = None,
) -> tuple[str | None, list[dict[str, Any]] | None]:
    options = options or SnapshotOptions(include_color_frequencies=True, capture_screenshot=True)
    if output_image_path is None and options.capture_screenshot:
        session_key = session_id or "default"
        output_image_path = os.path.join(get_artifacts_dir(session_key), "prototype_screenshot.png")

    playwright, browser, page, temp_html_path, _ = create_render_page(
        html_content,
        base_path,
        options=options,
    )
    try:
        screenshot_path = None
        if options.capture_screenshot and output_image_path:
            screenshot_path = capture_full_page_screenshot(page, output_image_path)
        color_frequencies = None
        if options.include_color_frequencies and screenshot_path:
            color_frequencies = pixels_to_color_frequency(screenshot_path)
        return screenshot_path, color_frequencies
    finally:
        close_render_page(playwright, browser, temp_html_path)


def extract_prototype_state_snapshot(
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
    artifacts = capture_prototype_state_artifacts(
        html_content=html_content,
        base_path=base_path,
        output_json_path=output_json_path,
        options=options,
    )
    return artifacts.snapshot.to_dict()


def extract_prototype_css_overview(
    html_content: str,
    base_path: str,
    options: SnapshotOptions | None = None,
) -> dict[str, Any]:
    options = options or SnapshotOptions(capture_screenshot=False)
    playwright, browser, page, temp_html_path, _ = create_render_page(
        html_content,
        base_path,
        options=options,
    )
    try:
        return capture_css_overview(page)
    finally:
        close_render_page(playwright, browser, temp_html_path)
