from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw
from pathlib import Path

def image_to_array(image_source: str | Path) -> np.ndarray:
    """Load an image from a path and convert it into a clean RGB NumPy array.

    Args:
        image_source: File path or path-like object pointing to the image.

    Returns:
        A 3D NumPy array representing the RGB pixel matrix.

    Raises:
        RuntimeError: If the image cannot be read, found, or processed.
    """
    try:
        with open(image_source, "rb") as image_file:
            with Image.open(image_file) as image:
                return np.array(image.convert("RGB"))
    except (FileNotFoundError, PermissionError) as exc:
        raise RuntimeError(
            f"Error de acceso al archivo de imagen '{image_source}': {exc}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo procesar o decodificar la imagen '{image_source}': {exc}"
        ) from exc

def build_histogram(
    image_rgb: np.ndarray,
    excluded_quads: list[list[tuple[float, float]]] | None = None
) -> dict[str, int]:
    """Calculate the frequency of unique RGB colors from an image matrix.

    Args:
        image_rgb: A 3D NumPy array representing the RGB pixel matrix.
        excluded_quads: Optional list of structured quads, where each quad 
          contains 4 coordinate tuples [(x1,y1), (x2,y2), (x3,y3), (x4,y4)].

    Returns:
        A dictionary mapping color strings to their pixel counts, 
        ordered from highest to lowest frequency.
    """
    height, width = image_rgb.shape[:2]

    # 1. Set the default fallback mask (include all pixels)
    mask = np.ones((height, width), dtype=bool)

    # 2. Apply exclusions geometrically if quads are provided
    if excluded_quads:
        mask_image = Image.new("1", (width, height), 1)
        draw = ImageDraw.Draw(mask_image)

        for points in excluded_quads:
            if len(points) != 4:
                continue
            draw.polygon(points, fill=0)

        mask = np.asarray(mask_image, dtype=bool)

    # 3. Extract only the layout pixels matching the 'True' zones of the mask
    valid_pixels = image_rgb[mask]

    # 4. Group exact identical colors and extract their absolute occurrence count
    unique_colors, counts = np.unique(valid_pixels, axis=0, return_counts=True)

    # 5. Zip and sort the raw arrays directly before allocating Python objects
    # Esto es mucho más eficiente que meter todo a listas y luego ordenarlas
    sorted_indices = np.argsort(-counts)  # El signo menos fuerza orden descendente
    
    unique_colors = unique_colors[sorted_indices]
    counts = counts[sorted_indices]

    # 6. Build the final dictionary in a single pass
    color_frequencies = {}
    for color, count in zip(unique_colors, counts):
        rgb_string = f"rgb({color[0]}, {color[1]}, {color[2]})"
        color_frequencies[rgb_string] = int(count)

    return color_frequencies
