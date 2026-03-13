from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from engine.rendering.models.snapshot_models import RenderArtifacts, SnapshotOptions
from engine.rendering.services.render_snapshot_service import capture_page_artifacts


def capture_page_artifacts_pipeline(
    html_content: str,
    base_path: str,
    *,
    output_image: str | None = None,
    output_json_path: str | None = None,
    session_id: str | None = None,
    include_color_frequencies: bool = False,
    trace: Any | None = None,
    label: str = "gui",
) -> RenderArtifacts:
    if trace:
        trace.add_step(f"{label}.render_start", {"base_path": base_path, "output_image": output_image})

    artifacts = capture_page_artifacts(
        html_content=html_content,
        base_path=base_path,
        session_id=session_id,
        output_json_path=output_json_path,
        output_image_path=output_image,
        options=SnapshotOptions(include_color_frequencies=include_color_frequencies),
    )

    if trace:
        trace.add_step(
            f"{label}.render_done",
            {
                "screenshot_path": artifacts.screenshot_path,
                "snapshot_node_count": artifacts.snapshot.metadata.get("nodeCount"),
            },
        )
        if artifacts.color_frequencies is not None:
            trace.add_step(
                f"{label}.colors_classified",
                {"distinct_colors": len(artifacts.color_frequencies)},
            )

    return artifacts


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


def analyze_screenshot_to_color_data(
    html_content: str,
    base_path: str,
    output_image: str | None = None,
    session_id: str | None = None,
    trace: Any | None = None,
    label: str = "gui",
) -> list[dict[str, Any]]:
    artifacts = capture_page_artifacts_pipeline(
        html_content=html_content,
        base_path=base_path,
        output_image=output_image,
        session_id=session_id,
        include_color_frequencies=True,
        trace=trace,
        label=label,
    )
    return artifacts.color_frequencies or []


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract render snapshot JSON")
    parser.add_argument("--html", required=True, help="Path to input HTML file")
    parser.add_argument("--base-path", required=True, help="Base path to resolve assets")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument(
        "--skip-invisible",
        action="store_true",
        help="Skip invisible nodes from output",
    )
    parser.add_argument(
        "--exclude-user-agent",
        action="store_true",
        help="Exclude user-agent rules from style trace output",
    )

    args = parser.parse_args()
    html_content = Path(args.html).read_text(encoding="utf-8")
    snapshot = extract_render_snapshot(
        html_content=html_content,
        base_path=args.base_path,
        output_json_path=args.output,
        options=SnapshotOptions(
            include_invisible=not args.skip_invisible,
            include_user_agent_rules=not args.exclude_user_agent,
            capture_screenshot=False,
        ),
    )
    print(json.dumps({"output": args.output, "nodeCount": snapshot["metadata"]["nodeCount"]}, indent=2))


if __name__ == "__main__":
    main()
