import numpy as np

def extract_pixels(image_array):
    """
    Convierte una imagen numpy (H,W,3) o (H,W,4) en lista Nx3 (RGB).
    P-LMLR usa solo RGB.
    """
    arr = np.asarray(image_array)

    # Si llega como (H,W,4) (RGBA), recorta a RGB
    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[:, :, :3]

    # Validación mínima
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"Formato de imagen no soportado para extract_pixels: shape={arr.shape}")

    return arr.reshape(-1, 3)
