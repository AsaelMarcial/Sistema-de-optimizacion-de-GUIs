import os
from typing import Any, Dict, Optional

from app.config import get_artifacts_dir

from engine.rendering.services.gui_rendering import render_gui
from engine.analysis.utils.pixel_utils import pixels_to_color_frequency


def analyze_screenshot_to_color_data(
    html_content: str,
    base_path: str,
    output_image: Optional[str] = None,
    session_id: Optional[str] = None,
    trace: Optional[Any] = None,
    label: str = "gui"
) -> Dict[str, Any]:
    """
    Pipeline: render (con base_path como raíz de recursos) -> color frequencies.
    """
    if trace:
        trace.add_step(f"{label}.render_start", {"base_path": base_path, "output_image": output_image})

    if output_image is None:
        default_output_dir = get_artifacts_dir(session_id or "default")
        os.makedirs(default_output_dir, exist_ok=True)
        output_image = os.path.join(default_output_dir, f"{label}_screenshot.png")

    screenshot_path = render_gui(
        html_content=html_content,
        base_path=base_path,
        output_image=output_image,
        session_id=session_id,
    )

    if trace:
        trace.add_step(f"{label}.render_done", {"screenshot_path": screenshot_path})

    color_data = pixels_to_color_frequency(screenshot_path)

    if trace:
        trace.add_step(
            f"{label}.colors_classified",
            {"distinct_colors": len(color_data) if hasattr(color_data, "__len__") else None}
        )

    return color_data
