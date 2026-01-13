import os
from typing import Any, Dict, Optional

from app.config import get_output_dir

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

    if output_image is None:
        default_output_dir = get_output_dir("default")
        os.makedirs(default_output_dir, exist_ok=True)
        output_image = os.path.join(default_output_dir, "gui_screenshot.png")
    pixels = analyze_gui(
        html_content=html_content,
        base_path=base_path,
        output_image=output_image
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
