from __future__ import annotations

from collections import Counter
from typing import Any

from engine.models.color_processing.color_processing_models import (
    PixelColorFrequency,
    PixelColorStatistic,
)
from engine.utils.image_utils import load_image_array


def pixels_to_color_frequency(image_source: Any) -> list[dict[str, Any]]:
    array = load_image_array(image_source)

    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError(f"Formato de imagen no soportado: shape={array.shape}")

    flat_pixels = array.reshape(-1, 3)
    color_counts = Counter(map(tuple, flat_pixels))

    return [
        PixelColorFrequency(color=tuple(color), count=count).to_dict()
        for color, count in color_counts.most_common()
    ]


def pixels_to_color_statistics(image_source: Any) -> list[dict[str, Any]]:
    frequencies = pixels_to_color_frequency(image_source)
    total_pixels = sum(item["count"] for item in frequencies)
    if total_pixels == 0:
        return []

    statistics: list[dict[str, Any]] = []
    for index, item in enumerate(frequencies, start=1):
        statistics.append(
            PixelColorStatistic(
                color_id=f"pixel-color-{index}",
                color=tuple(item["color"]),
                count=item["count"],
                percentage=round((item["count"] / total_pixels) * 100, 4),
            ).to_dict()
        )
    return statistics
