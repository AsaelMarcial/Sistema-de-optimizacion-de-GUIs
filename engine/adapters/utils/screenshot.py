from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from PIL import Image

from engine.adapters.color_service import color_registry
from engine.domain.models.color import PixelColorRecord


def load_image_array(image_source: Any) -> np.ndarray:
    if isinstance(image_source, str):
        with Image.open(image_source) as image:
            image = image.convert("RGB")
            return np.array(image)

    array = np.asarray(image_source)
    if array.ndim == 3 and array.shape[2] == 4:
        return array[:, :, :3]
    return array


def _flatten_rgb_pixels(array: np.ndarray) -> np.ndarray:
    if array.ndim != 3 or array.shape[2] != 3:
        raise ValueError(f"Formato de imagen no soportado: shape={array.shape}")
    return array.reshape(-1, 3)


def _color_records_from_flat_pixels(flat_pixels: np.ndarray, *, source: str | None = None) -> list[PixelColorRecord]:
    color_counts = Counter(map(tuple, flat_pixels))
    return [
        PixelColorRecord(color=tuple(color), count=count, source=source)
        for color, count in color_counts.most_common()
    ]


def pixels_to_color_records(image_source: Any) -> list[PixelColorRecord]:
    array = load_image_array(image_source)
    return _color_records_from_flat_pixels(_flatten_rgb_pixels(array), source="raw")


def _coerce_rect(payload: Mapping[str, Any] | Sequence[float]) -> tuple[int, int, int, int] | None:
    if isinstance(payload, Mapping):
        left = int(float(payload.get("left") or payload.get("x") or 0))
        top = int(float(payload.get("top") or payload.get("y") or 0))
        width = int(float(payload.get("width") or 0))
        height = int(float(payload.get("height") or 0))
        right = int(float(payload.get("right") or (left + width)))
        bottom = int(float(payload.get("bottom") or (top + height)))
    else:
        values = tuple(int(float(item)) for item in payload)
        if len(values) != 4:
            return None
        left, top, right, bottom = values
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _apply_exclusion_mask(
    array: np.ndarray,
    excluded_rects: Iterable[Mapping[str, Any] | Sequence[float]] | None,
) -> np.ndarray:
    if not excluded_rects:
        return array

    height, width = array.shape[0], array.shape[1]
    mask = np.ones((height, width), dtype=bool)
    for payload in excluded_rects:
        rect = _coerce_rect(payload)
        if rect is None:
            continue
        left, top, right, bottom = rect
        left = max(0, min(left, width))
        right = max(0, min(right, width))
        top = max(0, min(top, height))
        bottom = max(0, min(bottom, height))
        if right <= left or bottom <= top:
            continue
        mask[top:bottom, left:right] = False
    return array[mask]


def cluster_color_records(
    records: Sequence[PixelColorRecord],
    *,
    distance_threshold: float = 6.0,
) -> list[PixelColorRecord]:
    clustered: list[PixelColorRecord] = []
    for record in sorted(records, key=lambda item: item.count, reverse=True):
        matched_index: int | None = None
        matched_distance: float | None = None
        for index, candidate in enumerate(clustered):
            distance = color_registry.delta_e_distance(record.color, candidate.color, method="2000")
            if distance <= distance_threshold and (
                matched_distance is None or distance < matched_distance
            ):
                matched_index = index
                matched_distance = distance
        if matched_index is None:
            clustered.append(
                PixelColorRecord(
                    color=record.color,
                    count=record.count,
                    alpha=record.alpha,
                    source=record.source or "display",
                    metadata=dict(record.metadata or {}),
                )
            )
            continue

        existing = clustered[matched_index]
        metadata = dict(existing.metadata or {})
        metadata["clustered"] = True
        metadata["cluster_size"] = int(metadata.get("cluster_size") or 1) + 1
        clustered[matched_index] = PixelColorRecord(
            color=existing.color,
            count=existing.count + record.count,
            alpha=existing.alpha,
            source=existing.source or "display",
            metadata=metadata,
        )
    return clustered


def pixels_to_display_color_records(
    image_source: Any,
    *,
    excluded_rects: Iterable[Mapping[str, Any] | Sequence[float]] | None = None,
    cluster_distance: float = 6.0,
) -> list[PixelColorRecord]:
    array = load_image_array(image_source)
    filtered_pixels = _apply_exclusion_mask(array, excluded_rects)
    if getattr(filtered_pixels, "size", 0) == 0:
        return []
    if filtered_pixels.ndim == 3:
        filtered_pixels = _flatten_rgb_pixels(filtered_pixels)
    if filtered_pixels.ndim == 1:
        filtered_pixels = filtered_pixels.reshape(-1, 3)
    records = _color_records_from_flat_pixels(filtered_pixels, source="display")
    return cluster_color_records(records, distance_threshold=cluster_distance)


def pixels_to_color_frequency(image_source: Any) -> list[dict[str, Any]]:
    return [record.to_dict() for record in pixels_to_color_records(image_source)]


def pixels_to_display_color_frequency(
    image_source: Any,
    *,
    excluded_rects: Iterable[Mapping[str, Any] | Sequence[float]] | None = None,
    cluster_distance: float = 6.0,
) -> list[dict[str, Any]]:
    return [
        record.to_dict()
        for record in pixels_to_display_color_records(
            image_source,
            excluded_rects=excluded_rects,
            cluster_distance=cluster_distance,
        )
    ]
