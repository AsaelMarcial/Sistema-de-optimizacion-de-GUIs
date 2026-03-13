from collections import defaultdict

from engine.analysis.utils.color_utils import calculate_reduction


def evaluate_and_apply_heuristics(*args, **kwargs):
    from engine.transformation.services.heuristic_evaluator import (  # deferred import to avoid cycle
        evaluate_and_apply_heuristics as _evaluate_and_apply_heuristics,
    )

    return _evaluate_and_apply_heuristics(*args, **kwargs)


def build_heuristics_results(sustainable_components):
    heuristics_dict = defaultdict(lambda: {"detalles": [], "comparativas": []})

    for component in sustainable_components:
        ahorro = calculate_reduction(component["before_rgb"], component["after_rgb"])

        heuristics_dict[component["heuristic"]]["comparativas"].append(
            {
                "nombre": component["nombre"],
                "antes": f"{component['before_rgb'][0]}, {component['before_rgb'][1]}, {component['before_rgb'][2]}",
                "despues": f"{component['after_rgb'][0]}, {component['after_rgb'][1]}, {component['after_rgb'][2]}",
                "ahorro": ahorro,
            }
        )

    heuristics_results = []
    for heuristic_name, data in heuristics_dict.items():
        detalles = [
            (
                f"{component['nombre']}: color antes RGB({component['antes']}) → después RGB({component['despues']}) | "
                f"Ahorro estimado: {component['ahorro']}%"
            )
            for component in data["comparativas"]
        ]
        heuristics_results.append(
            {
                "nombre": heuristic_name,
                "cumple": True,
                "recomendacion": (
                    f"Se han transformado {len(data['comparativas'])} componentes bajo la heurística "
                    f"'{heuristic_name}'."
                ),
                "detalles": detalles,
                "comparativas": data["comparativas"],
            }
        )

    return heuristics_results


# Backward-compatible alias (temporary)
evaluar_y_corregir_heuristicas = evaluate_and_apply_heuristics

__all__ = [
    "evaluate_and_apply_heuristics",
    "evaluar_y_corregir_heuristicas",
    "build_heuristics_results",
]
