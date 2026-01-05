from typing import Any, Dict, Optional

from utils.gui_analyzer import analyze_gui
from utils.pixel_processor import extract_pixels
from utils.color_classifier import classify_colors


def analyze_gui_to_color_data(
    html_content: str,
    base_path: str,
    trace: Optional[Any] = None,
    label: str = "gui"
) -> Dict[str, Any]:
    """
    Pipeline: render GUI -> pixels -> color frequencies.
    `trace` es opcional (DebugTrace). Si viene, registra pasos.
    """
    if trace:
        trace.add_step(f"{label}.render_start", {"base_path": base_path})

    pixels = analyze_gui(html_content, base_path=base_path)

    if trace:
        trace.add_step(f"{label}.render_done", {"pixels_type": str(type(pixels))})

    extracted = extract_pixels(pixels)

    if trace:
        trace.add_step(f"{label}.pixels_extracted", {
            "count": len(extracted) if hasattr(extracted, "__len__") else None
        })

    color_data = classify_colors(extracted)

    if trace:
        trace.add_step(f"{label}.colors_classified", {
            "distinct_colors": len(color_data) if hasattr(color_data, "__len__") else None
        })

    return color_data
