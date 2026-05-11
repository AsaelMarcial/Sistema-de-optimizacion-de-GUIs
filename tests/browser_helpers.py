from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.browser.css_overview import build_css_overview_from_models
from engine.adapters.browser.render_models import RenderSnapshot, SnapshotOptions
from engine.domain.models.color import ColorCatalog
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.style import StyleCatalog
from engine.domain.utils.color_usage import build_color_usage_catalog


@dataclass(frozen=True, slots=True)
class CapturedPrototypeState:
    screenshot_path: str | None
    snapshot: RenderSnapshot
    style_catalog: StyleCatalog
    colors_inventory: ColorCatalog


def capture_prototype_state_artifacts(
    html_content: str,
    base_path: str,
    *,
    options: SnapshotOptions | None = None,
    artifacts_dir: str | None = None,
    screenshot_filename: str | None = None,
    page_builder: PageBuilder | None = None,
    session_id: str | None = None,
) -> CapturedPrototypeState:
    options = options or SnapshotOptions()
    if session_id and artifacts_dir is None:
        artifacts_path = Path("workspace") / "sessions" / f"session_{session_id}" / "artifacts"
        artifacts_path.mkdir(parents=True, exist_ok=True)
        artifacts_dir = str(artifacts_path)
        screenshot_filename = screenshot_filename or "before.png"
    owns_page_builder = page_builder is None
    builder = page_builder or PageBuilder.new(
        html_content,
        base_path,
        options=options,
    )
    try:
        screenshot_path = None
        if artifacts_dir and screenshot_filename:
            screenshot_path = builder.capture_full_page_screenshot(
                output_path=str(Path(artifacts_dir) / Path(screenshot_filename).name),
            )
        snapshot, style_catalog, colors_inventory = builder.capture_snapshot_models()
        return CapturedPrototypeState(
            screenshot_path=screenshot_path,
            snapshot=snapshot,
            style_catalog=style_catalog,
            colors_inventory=colors_inventory,
        )
    finally:
        if owns_page_builder:
            builder.close()


def extract_prototype_state_snapshot(
    html_content: str,
    base_path: str,
    options: SnapshotOptions | None = None,
) -> dict[str, Any]:
    options = replace(options, capture_screenshot=False) if options else SnapshotOptions(capture_screenshot=False)
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
    builder = PageBuilder.new(
        html_content,
        base_path,
        options=options,
    )
    try:
        snapshot, styles_inventory, colors_inventory = builder.capture_snapshot_models()
    finally:
        builder.close()
    prototype_structure = PrototypeStructure.build(snapshot.nodes)
    colors_inventory = build_color_usage_catalog(
        prototype_structure,
        existing_inventory=ColorCatalog.build(colors_inventory),
    )
    return build_css_overview_from_models(
        prototype_structure,
        styles_inventory,
        colors_inventory,
    )
