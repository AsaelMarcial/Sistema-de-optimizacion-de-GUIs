from collections import Counter

import numpy as np
from PIL import Image


def pixels_to_color_frequency(image_source):
    """
    Convierte una imagen (ruta o np.ndarray) en frecuencias de color RGB.
    """
    if isinstance(image_source, str):
        with Image.open(image_source) as img:
            img = img.convert("RGB")
            arr = np.array(img)
    else:
        arr = np.asarray(image_source)

    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[:, :, :3]

    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"Formato de imagen no soportado: shape={arr.shape}")

    flat_pixels = arr.reshape(-1, 3)
    color_counts = Counter(map(tuple, flat_pixels))
    sorted_colors = color_counts.most_common()

    return [{"color": list(color), "count": count} for color, count in sorted_colors]
