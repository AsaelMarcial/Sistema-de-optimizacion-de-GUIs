from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
from PIL import Image


def json_default_numpy_serializer(obj: Any):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Tipo de objeto {obj.__class__.__name__} no serializable")


def pixels_to_color_frequency(image_source: Any) -> list[dict[str, Any]]:
    if isinstance(image_source, str):
        with Image.open(image_source) as image:
            image = image.convert("RGB")
            array = np.array(image)
    else:
        array = np.asarray(image_source)

    if array.ndim == 3 and array.shape[2] == 4:
        array = array[:, :, :3]

    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError(f"Formato de imagen no soportado: shape={array.shape}")

    flat_pixels = array.reshape(-1, 3)
    color_counts = Counter(map(tuple, flat_pixels))

    return [
        {"color": list(color), "count": count}
        for color, count in color_counts.most_common()
    ]
