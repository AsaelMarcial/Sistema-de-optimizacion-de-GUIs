import numpy as np

def extract_pixels(image_array):
    """
    Convierte np.ndarray (H,W,3) o (H,W,4) en lista Nx3 RGB.
    P-LMLR usa solo RGB.
    """
    arr = np.asarray(image_array)

    if arr.ndim == 3 and arr.shape[2] == 4:
        arr = arr[:, :, :3]

    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"Formato de imagen no soportado: shape={arr.shape}")

    return arr.reshape(-1, 3).tolist()
