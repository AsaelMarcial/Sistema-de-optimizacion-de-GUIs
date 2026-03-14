from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image


def load_image_array(image_source: Any) -> np.ndarray:
    if isinstance(image_source, str):
        with Image.open(image_source) as image:
            image = image.convert("RGB")
            return np.array(image)

    array = np.asarray(image_source)
    if array.ndim == 3 and array.shape[2] == 4:
        return array[:, :, :3]
    return array
