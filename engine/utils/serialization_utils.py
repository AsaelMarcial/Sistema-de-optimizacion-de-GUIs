from __future__ import annotations

from typing import Any

import numpy as np


def json_default_numpy_serializer(obj: Any) -> list[Any]:
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Tipo de objeto {obj.__class__.__name__} no serializable")
