from __future__ import annotations

from typing import Mapping, Sequence

from engine.domain.models.color import PixelColorRecord


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def color_frequency_to_statistics(
    frequencies: Sequence[Mapping[str, object] | PixelColorRecord],
) -> list[dict[str, object]]:
    normalized_frequencies = [
        item if isinstance(item, PixelColorRecord) else PixelColorRecord.from_mapping(item)
        for item in frequencies
    ]
    total_pixels = sum(item.count for item in normalized_frequencies)
    if total_pixels == 0:
        return []

    statistics: list[dict[str, object]] = []
    for index, item in enumerate(normalized_frequencies, start=1):
        statistics.append(
            PixelColorRecord(
                color_id=f"pixel-color-{index}",
                color=item.color,
                count=item.count,
                percentage=round((item.count / total_pixels) * 100, 4),
            ).to_dict()
        )
    return statistics
