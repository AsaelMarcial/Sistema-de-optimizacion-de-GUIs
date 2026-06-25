from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import tempfile
from typing import Any

from engine.adapters.browser.page_builder import PageBuilder
from engine.adapters.browser.render_models import RenderSnapshot, SnapshotOptions
from engine.domain.models.color import ColorCatalog
from engine.domain.models.prototype_structure import PrototypeStructure
from engine.domain.models.quality_reports import ColorUsages
from engine.domain.models.style import StyleCatalog


@dataclass(frozen=True, slots=True)
class CapturedPrototypeState:
    screenshot_path: str | None
    snapshot: RenderSnapshot
    style_catalog: StyleCatalog
    colors_inventory: ColorCatalog
    color_usages: ColorUsages


def _build_color_state(
    snapshot: RenderSnapshot,
) -> tuple[RenderSnapshot, PrototypeStructure, ColorCatalog, ColorUsages]:
    prototype_structure = PrototypeStructure.build(snapshot.nodes)
    color_catalog = ColorCatalog()
    color_usages = ColorUsages()
    for element in prototype_structure:
        for property_model in element.properties:
            property_id = property_model.property_id or property_model.name
            color_ids: list[str] = []
            color_values = property_model.color_values()
            for color_value in color_values:
                color_id = color_catalog.add_color(color_value)
                color_ids.append(color_id)
                color_usages.add(
                    color_id=color_id,
                    property_name=property_id,
                    element_id=element.node_id,
                )
            property_model.set_color_ids(color_ids)
    return (
        RenderSnapshot(
            metadata=snapshot.metadata,
            document=snapshot.document,
            nodes=prototype_structure.nodes,
        ),
        prototype_structure,
        color_catalog,
        color_usages,
    )


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
    html_path: Path | None = None
    if page_builder is None:
        base_dir = Path(base_path).resolve()
        base_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".html",
            prefix="test_render_",
            dir=base_dir,
            delete=False,
        ) as html_file:
            html_file.write(html_content)
            html_path = Path(html_file.name)
        builder = PageBuilder.new_from_file(html_path, options=options)
    else:
        builder = page_builder
    try:
        screenshot_path = None
        if artifacts_dir and screenshot_filename:
            screenshot_path = builder.capture_fullpage_screenshot(
                output_path=str(Path(artifacts_dir) / Path(screenshot_filename).name),
            )
        snapshot, style_catalog = builder.capture_snapshot_models()
        snapshot, _prototype_structure, colors_inventory, color_usages = _build_color_state(snapshot)
        return CapturedPrototypeState(
            screenshot_path=screenshot_path,
            snapshot=snapshot,
            style_catalog=style_catalog,
            colors_inventory=colors_inventory,
            color_usages=color_usages,
        )
    finally:
        if owns_page_builder:
            builder.close()
        if html_path is not None and html_path.exists():
            html_path.unlink()


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
