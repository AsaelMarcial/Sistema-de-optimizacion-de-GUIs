from __future__ import annotations

from os import PathLike
from typing import Any, Iterable, Mapping, TypeAlias

import numpy as np
from PIL import Image

from engine.adapters.color_service import color_registry

ColorHistogram: TypeAlias = list[dict[str, Any]]
_Box: TypeAlias = tuple[int, int, int, int]


def load_image_array(image_source: Any) -> np.ndarray:
    if isinstance(image_source, (str, PathLike)):
        with open(image_source, "rb") as image_file:
            with Image.open(image_file) as image:
                converted = image.convert("RGB")
                try:
                    return np.array(converted)
                finally:
                    converted.close()

    if isinstance(image_source, Image.Image):
        converted = image_source.convert("RGB")
        try:
            return np.array(converted)
        finally:
            converted.close()

    return _drop_alpha_channel(np.asarray(image_source))


def build_color_histograms(
    image_source: Any,
    *,
    prototype_structure: Any = None,
    cluster_distance: float = 6.0,
) -> dict[str, ColorHistogram]:
    image = load_image_array(image_source)
    environmental_histogram = _color_histogram_from_array(image)
    scheme_histogram = environmental_histogram

    if prototype_structure is not None:
        excluded_boxes = tuple(prototype_structure.excluded_pixel_boxes())
        if excluded_boxes:
            excluded_histogram = _color_histogram_from_boxes(image, excluded_boxes)
            scheme_histogram = _subtract_color_histograms(
                environmental_histogram,
                excluded_histogram,
            )

    return {
        "environmental": environmental_histogram,
        "scheme": cluster_color_histogram(
            scheme_histogram,
            cluster_distance=cluster_distance,
        ),
    }


def cluster_color_histogram(
    color_histogram: Iterable[Mapping[str, Any]],
    *,
    cluster_distance: float = 6.0,
) -> ColorHistogram:
    clustered: ColorHistogram = []
    for row in sorted(
        (_color_histogram_row(item) for item in color_histogram),
        key=lambda item: int(item["count"]),
        reverse=True,
    ):
        row_color = _color_key(row["color"])
        matched_index: int | None = None
        matched_distance: float | None = None
        for index, candidate in enumerate(clustered):
            distance = color_registry.delta_e_distance(
                row_color,
                _color_key(candidate["color"]),
                method="2000",
            )
            if distance <= cluster_distance and (
                matched_distance is None or distance < matched_distance
            ):
                matched_index = index
                matched_distance = distance

        if matched_index is None:
            clustered.append(row)
            continue

        clustered[matched_index] = {
            "color": list(clustered[matched_index]["color"]),
            "count": int(clustered[matched_index]["count"]) + int(row["count"]),
        }
    return clustered


def get_color_count(
    color_histogram: Iterable[Mapping[str, Any]],
    r: int,
    g: int,
    b: int,
    *,
    distance_threshold: float = 6.0,
) -> dict[str, Any]:
    target = (int(r), int(g), int(b))
    best_row: dict[str, Any] | None = None
    best_distance: float | None = None

    for item in color_histogram:
        row = _color_histogram_row(item)
        row_color = _color_key(row["color"])
        if row_color == target:
            return row

        distance = color_registry.delta_e_distance(
            target,
            row_color,
            method="2000",
        )
        if distance > distance_threshold:
            continue
        if best_distance is None or distance < best_distance:
            best_row = row
            best_distance = distance

    return best_row or {"color": list(target), "count": 0}


def color_histogram_total(color_histogram: Iterable[Mapping[str, Any]]) -> int:
    return sum(int(item.get("count") or 0) for item in color_histogram)


def dominant_color_percentages(
    color_histogram: Iterable[Mapping[str, Any]],
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    rows = sorted(
        (_color_histogram_row(item) for item in color_histogram),
        key=lambda item: int(item["count"]),
        reverse=True,
    )
    total = color_histogram_total(rows)
    if total <= 0:
        return []

    return [
        {
            "color": list(row["color"]),
            "count": int(row["count"]),
            "percentage": round((int(row["count"]) / total) * 100, 4),
        }
        for row in rows[: max(int(limit), 0)]
    ]


def _drop_alpha_channel(array: np.ndarray) -> np.ndarray:
    if array.ndim == 3 and array.shape[2] == 4:
        return array[:, :, :3]
    return array


def _color_histogram_from_array(array: np.ndarray) -> ColorHistogram:
    pixels = _drop_alpha_channel(np.asarray(array))
    if pixels.ndim == 3 and pixels.shape[2] == 3:
        pixels = pixels.reshape(-1, 3)
    elif pixels.ndim == 2 and pixels.shape[1] == 3:
        pixels = pixels
    elif pixels.ndim == 1 and pixels.size % 3 == 0:
        pixels = pixels.reshape(-1, 3)
    else:
        raise ValueError(f"Formato de imagen no soportado: shape={pixels.shape}")

    if pixels.size == 0:
        return []

    colors, first_seen, counts = np.unique(
        pixels,
        axis=0,
        return_counts=True,
        return_index=True,
    )
    order = np.lexsort((first_seen, -counts))
    return [
        {"color": [int(channel) for channel in colors[index]], "count": int(counts[index])}
        for index in order
    ]


def _color_histogram_from_boxes(
    image: np.ndarray,
    boxes: Iterable[_Box],
) -> ColorHistogram:
    image = _drop_alpha_channel(np.asarray(image))
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError(f"Formato de imagen no soportado: shape={image.shape}")

    image_height, image_width = image.shape[:2]
    mask = np.zeros((image_height, image_width), dtype=bool)
    for box in boxes:
        clipped_box = _clip_box(
            box,
            image_width=image_width,
            image_height=image_height,
        )
        if clipped_box is None:
            continue
        left, top, right, bottom = clipped_box
        mask[top:bottom, left:right] = True

    if not mask.any():
        return []
    return _color_histogram_from_array(image[mask])


def _subtract_color_histograms(
    base_histogram: Iterable[Mapping[str, Any]],
    removed_histogram: Iterable[Mapping[str, Any]],
) -> ColorHistogram:
    counts = _counts_by_color(base_histogram)
    for color, removed_count in _counts_by_color(removed_histogram).items():
        remaining_count = counts.get(color, 0) - removed_count
        if remaining_count > 0:
            counts[color] = remaining_count
        else:
            counts.pop(color, None)

    return [
        {"color": list(color), "count": count}
        for color, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]


def _counts_by_color(color_histogram: Iterable[Mapping[str, Any]]) -> dict[tuple[int, int, int], int]:
    counts: dict[tuple[int, int, int], int] = {}
    for item in color_histogram:
        row = _color_histogram_row(item)
        color = _color_key(row["color"])
        counts[color] = counts.get(color, 0) + int(row["count"])
    return counts


def _color_histogram_row(item: Mapping[str, Any]) -> dict[str, Any]:
    return {"color": list(_color_key(item.get("color"))), "count": int(item.get("count") or 0)}


def _color_key(color: object) -> tuple[int, int, int]:
    if color is None or isinstance(color, (str, bytes)):
        raise ValueError(f"Color invalido: {color!r}")
    try:
        rgb = tuple(int(channel) for channel in color)  # type: ignore[union-attr]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Color invalido: {color!r}") from exc
    if len(rgb) != 3:
        raise ValueError(f"Color invalido: {color!r}")
    return rgb


def _clip_box(
    box: _Box,
    *,
    image_width: int,
    image_height: int,
) -> _Box | None:
    left, top, right, bottom = box
    left = max(0, min(int(left), image_width))
    right = max(0, min(int(right), image_width))
    top = max(0, min(int(top), image_height))
    bottom = max(0, min(int(bottom), image_height))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom
