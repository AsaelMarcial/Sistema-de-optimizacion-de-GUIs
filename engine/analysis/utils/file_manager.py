import json

from engine.analysis.utils.pixel_utils import json_default_numpy_serializer


def save_results(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, default=json_default_numpy_serializer)
