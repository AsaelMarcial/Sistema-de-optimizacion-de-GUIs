def classify_colors(pixel_array):
    """
    Clasifica los colores predominantes basados en el array de píxeles.
    """
    from collections import Counter

    # Contar los colores
    color_counts = Counter([tuple(pixel) for pixel in pixel_array])  # Convertir en tuplas
    sorted_colors = color_counts.most_common()

    # Convertir los colores a listas (serializables)
    return [{"color": list(color), "count": count} for color, count in sorted_colors]
