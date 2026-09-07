# app/Exceptions/custom-mesagges.py
from types import MappingProxyType

# Volvemos a la estructura plana, inmutable y limpia que preferías
MESSAGES = MappingProxyType(
    {
        "MULTIPLE_HTML": "No se permite más de un archivo HTML.",
        "MULTIPLE_ZIP": "No se permite más de un archivo ZIP.",
        "INTERNAL_ZIP_FILE": "Un archivo interno del ZIP no es válido.",
        "SECURITY_VIOLATION": "Se detectó un archivo binario ejecutable prohibido.",
        "CORRUPTED_ASSET": "El archivo subido está corrupto o no se puede leer.",
        "MISSING_HTML": "Se necesita subir al menos un archivo HTML para procesar el proyecto.",
        "MISSING_UPLOAD": "No se ha subido ningún archivo.",
        "INVALID_FILE_TYPE": "El tipo de archivo no es válido.",
    }
)
