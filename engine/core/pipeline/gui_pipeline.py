from typing import Any, Dict, Optional

from engine.rendering.screenshot_analyzer import analyze_screenshot_to_color_data


def analyze_gui_to_color_data(
    html_content: str,
    base_path: str,
    output_image: Optional[str] = None,
    session_id: Optional[str] = None,
    trace: Optional[Any] = None,
    label: str = "gui"
) -> Dict[str, Any]:
    """
    Pipeline: render (con base_path como raíz de recursos) -> pixels -> color frequencies.
    """
    return analyze_screenshot_to_color_data(
        html_content=html_content,
        base_path=base_path,
        output_image=output_image,
        session_id=session_id,
        trace=trace,
        label=label
    )
