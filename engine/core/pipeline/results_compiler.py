from typing import Any, Dict, Optional

from engine.analysis.utils.file_manager import save_results


def compile_results(
    *,
    total_current: float,
    footprint: Dict[str, Any],
    environmental_assessment: Dict[str, Any],
    session_id: str,
    html_filename: str,
    heuristics_results: Any,
    trace: Optional[Any],
    original_screenshot_rel: str,
    environmental_screenshot_rel: str,
    session_dirname: str,
    results_output_path: Optional[str] = None,
) -> Dict[str, Any]:
    results = {
        "total_current": total_current,
        "carbon_footprint": footprint["co2eq_per_use"],
        "energy_wh": footprint["energy_wh"],
        "environmental_energy_wh": environmental_assessment["energy_wh"],
        "environmental_co2eq_per_use": environmental_assessment["co2eq_per_use"],
        "session_id": session_id,
        "session_dirname": session_dirname,
        "html_name": html_filename,
        "heuristics": heuristics_results,
        "heuristicas": heuristics_results,
        "debug": trace.to_dict() if trace else None,
        "debug_screenshots": {
            "original": original_screenshot_rel,
            "environmental": environmental_screenshot_rel,
        },
    }

    if results_output_path:
        save_results(results_output_path, results)

    return results


def build_results_payload(**kwargs):
    return compile_results(**kwargs)
