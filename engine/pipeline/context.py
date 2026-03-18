from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.domain.models.snapshot import RenderArtifacts
from engine.models.file_handling.project_input import ProjectInput
from engine.models.file_handling.session_workspace import SessionWorkspace
from engine.models.recommendations.recommendations_payload import RecommendationsPayload
from engine.pipeline.debug_trace import DebugTrace


@dataclass(slots=True)
class PipelineContext:
    file: Any | None
    trace: DebugTrace = field(default_factory=lambda: DebugTrace(enabled=True))
    session_id: str | None = None
    project_input: ProjectInput | None = None
    workspace: SessionWorkspace | None = None
    base_path: str | None = None
    html_path: str | None = None
    html_filename: str | None = None
    html_content: str | None = None
    output_dir: str | None = None
    artifacts_dir: str | None = None
    session_dirname: str | None = None
    original_snapshot_path: str | None = None
    original_screenshot_path: str | None = None
    original_screenshot_rel: str = "debug_original.png"
    transformed_html_path: str | None = None
    transformed_html_content: str | None = None
    environmental_screenshot_path: str | None = None
    environmental_screenshot_rel: str = "debug_environmental.png"
    palette_preview_output_path: str | None = None
    palette_preview_rel: str = "palette_preview.png"
    results_output_path: str | None = None
    palette_analysis_output_path: str | None = None
    zip_output_path: str | None = None
    zip_filename: str | None = None
    zip_download_url: str | None = None
    original_artifacts: RenderArtifacts | None = None
    environmental_artifacts: RenderArtifacts | None = None
    footprint: dict[str, Any] | None = None
    environmental_assessment: dict[str, Any] | None = None
    heuristics_results: list[dict[str, Any]] | None = None
    recommendations: RecommendationsPayload | None = None
    results: dict[str, Any] | None = None
    color_processing_input: Any | None = None
    pixel_color_frequencies: list[dict[str, Any]] | None = None
    pixel_color_statistics: list[dict[str, Any]] | None = None
    palette_analysis: dict[str, Any] | None = None
    error: str | None = None
