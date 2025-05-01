import json
import numpy as np

def save_results(path, data):
    # Convertir las matrices de píxeles a listas de enteros antes de serializarlas
    def convert_np_array(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()  # Convierte el numpy array en una lista
        raise TypeError(f"Tipo de objeto {obj.__class__.__name__} no serializable")
    
    # Guardar los resultados en formato JSON
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, default=convert_np_array)
