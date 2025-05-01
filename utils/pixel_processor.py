def extract_pixels(image_array):
    """
    Convierte la matriz de píxeles de la imagen (np.ndarray) a una lista de tuplas que son serializables a JSON.
    """
    return image_array.reshape(-1, 3).tolist()  # Convierte a una lista de listas (serializable)
