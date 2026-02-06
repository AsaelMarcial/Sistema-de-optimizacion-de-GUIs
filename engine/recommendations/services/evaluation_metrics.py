from collections import defaultdict


def luminance(rgb):
    r, g, b = [x / 255.0 for x in rgb]
    return 0.2126 * (r**3) + 0.7152 * (g**3) + 0.0722 * (b**3)


def calculate_reduction(before_rgb, after_rgb):
    initial_lum = luminance(before_rgb)
    sustainable_lum = luminance(after_rgb)
    if initial_lum == 0:
        return 0.0
    reduction = ((initial_lum - sustainable_lum) / initial_lum) * 100
    return round(reduction, 2)


def build_heuristics_results(sustainable_components):
    heuristics_dict = defaultdict(lambda: {"detalles": [], "comparativas": []})

    for comp in sustainable_components:
        ahorro = calculate_reduction(comp["before_rgb"], comp["after_rgb"])

        heuristics_dict[comp["heuristic"]]["comparativas"].append(
            {
                "nombre": comp["nombre"],
                "antes": f"{comp['before_rgb'][0]}, {comp['before_rgb'][1]}, {comp['before_rgb'][2]}",
                "despues": f"{comp['after_rgb'][0]}, {comp['after_rgb'][1]}, {comp['after_rgb'][2]}",
                "ahorro": ahorro,
            }
        )

    heuristics_results = []
    for heuristic_name, data in heuristics_dict.items():
        detalles = [
            (
                f"{comp['nombre']}: color antes RGB({comp['antes']}) → después RGB({comp['despues']}) | "
                f"Ahorro estimado: {comp['ahorro']}%"
            )
            for comp in data["comparativas"]
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
