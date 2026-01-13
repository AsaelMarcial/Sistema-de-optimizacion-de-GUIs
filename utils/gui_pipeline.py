from typing import Any, Dict, Optional

from engine.rendering.services.gui_analyzer import analyze_gui
from engine.rendering.utils.pixel_processor import extract_pixels
from engine.rendering.utils.color_classifier import classify_colors


def analyze_gui_to_color_data(
    html_content: str,
    base_path: str,
    output_image: Optional[str] = None,
    trace: Optional[Any] = None,
    label: str = "gui"
) -> Dict[str, Any]:
    """
    Pipeline: render (con base_path como raíz de recursos) -> pixels -> color frequencies.
    """
    if trace:
        trace.add_step(f"{label}.render_start", {"base_path": base_path, "output_image": output_image})

    pixels = analyze_gui(
        html_content=html_content,
        base_path=base_path,
        output_image=output_image or "data/output/gui_screenshot.png"
    )

    if trace:
        trace.add_step(f"{label}.render_done", {"pixels_shape": getattr(pixels, "shape", None)})

    extracted = extract_pixels(pixels)

    if trace:
        trace.add_step(f"{label}.pixels_extracted", {"count": len(extracted) if hasattr(extracted, "__len__") else None})

    color_data = classify_colors(extracted)

    if trace:
        trace.add_step(f"{label}.colors_classified", {"distinct_colors": len(color_data) if hasattr(color_data, "__len__") else None})

    return color_data
