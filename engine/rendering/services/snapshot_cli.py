import argparse
import json
from pathlib import Path

from engine.rendering.services.render_snapshot_extractor import SnapshotOptions, extract_render_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract Module 1 render snapshot JSON")
    parser.add_argument("--html", required=True, help="Path to input HTML file")
    parser.add_argument("--base-path", required=True, help="Base path to resolve assets")
    parser.add_argument("--output", required=True, help="Path to output JSON file")
    parser.add_argument(
        "--skip-invisible",
        action="store_true",
        help="Skip invisible nodes from output",
    )

    args = parser.parse_args()
    html_path = Path(args.html)
    html_content = html_path.read_text(encoding="utf-8")

    snapshot = extract_render_snapshot(
        html_content=html_content,
        base_path=args.base_path,
        output_json_path=args.output,
        options=SnapshotOptions(include_invisible=not args.skip_invisible),
    )

    print(json.dumps({"output": args.output, "nodeCount": snapshot["metadata"]["nodeCount"]}, indent=2))


if __name__ == "__main__":
    main()
