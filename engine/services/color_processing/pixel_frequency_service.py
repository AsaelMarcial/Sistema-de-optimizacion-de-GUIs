from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from engine.domain.models.color import PixelColorRecord
from engine.domain.utils.formatters import color_frequency_to_statistics
from engine.utils.image_utils import load_image_array


def pixels_to_color_records(image_source: Any) -> list[PixelColorRecord]:
    array = load_image_array(image_source)

    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError(f"Formato de imagen no soportado: shape={array.shape}")

    flat_pixels = array.reshape(-1, 3)
    color_counts = Counter(map(tuple, flat_pixels))
    return [
        PixelColorRecord(color=tuple(color), count=count)
        for color, count in color_counts.most_common()
    ]


def pixels_to_color_frequency(image_source: Any) -> list[dict[str, Any]]:
    return [record.to_dict() for record in pixels_to_color_records(image_source)]


def pixels_to_color_statistics(image_source: Any) -> list[dict[str, Any]]:
    frequencies = pixels_to_color_records(image_source)
    return color_frequency_to_statistics(frequencies)
